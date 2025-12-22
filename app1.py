# This code is for segmentation

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import uuid
import shutil
import tempfile
import zipfile
import threading

import SimpleITK as sitk
import dicom2nifti
from totalsegmentator.python_api import totalsegmentator

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# ---------------------------------------------------------------------
# Flask app + config
# ---------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# Limit upload size (example: 2 GB)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB

# Base directories (adjust if needed)
UPLOAD_DIR = "/mnt/external/Testing project/pythonProject2/upload"
RESULT_BASE_DIR = "/mnt/external/Testing project/pythonProject2/upload/result"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_BASE_DIR, exist_ok=True)

# In-memory job registry
# JOBS[case_id] = {
#   "status": "string",
#   "error": None or "error msg",
#   "zip_path": "/path/to/zip" or None,
#   "original_name": "patient-1.nrrd"
# }
JOBS = {}
JOBS_LOCK = threading.Lock()

# Lung lobe labels used by the "total" model
LUNG_LOBE_CLASSES = [
    "lung_upper_lobe_left",
    "lung_lower_lobe_left",
    "lung_upper_lobe_right",
    "lung_middle_lobe_right",
    "lung_lower_lobe_right",
]


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------
def update_job_status(case_id: str, status: str, error: str | None = None):
    """
    Update status for a job.
    If error is not None, also set the error field.
    """
    with JOBS_LOCK:
        if case_id not in JOBS:
            JOBS[case_id] = {}
        JOBS[case_id]["status"] = status
        if error is not None:  # only set error when explicitly provided
            JOBS[case_id]["error"] = error


def convert_nrrd_to_nifti(input_path: str, tmp_dir: str) -> str:
    """
    Convert NRRD to NIfTI (.nii.gz) using SimpleITK.
    """
    img = sitk.ReadImage(input_path)
    nifti_path = os.path.join(tmp_dir, "input_converted.nii.gz")
    sitk.WriteImage(img, nifti_path)
    return nifti_path


def convert_nii_to_nrrd(nii_path: str, out_dir: str) -> str:
    """
    Convert NIfTI (.nii or .nii.gz) to NRRD.
    Output filename keeps base + .nrrd.
    """
    img = sitk.ReadImage(nii_path)
    base = os.path.basename(nii_path)
    if base.endswith(".nii.gz"):
        base = base[:-7]
    elif base.endswith(".nii"):
        base = base[:-4]
    filename = base + ".nrrd"
    out_path = os.path.join(out_dir, filename)
    sitk.WriteImage(img, out_path)
    return out_path


def run_totalseg_lung(input_nii: str, case_result_dir: str, case_id: str):
    """
    Run TotalSegmentator for lung lobes:
    - Try GPU first (if available)
    - On any GPU error, fall back to CPU
    Only raise an exception if both GPU and CPU fail.
    """
    gpu_error_msg = None

    # ----------------- Try GPU first, if PyTorch + CUDA available -----------------
    if HAS_TORCH and torch.cuda.is_available():
        update_job_status(
            case_id,
            "Running lung segmentation on GPU (low-memory mode)..."
        )
        try:
            totalsegmentator(
                input=input_nii,
                output=case_result_dir,
                task="total",
                roi_subset=LUNG_LOBE_CLASSES,   # only lung lobes
                fast=True,                      # lower resolution (less memory, faster)
                body_seg=True,
                force_split=True,               # process in parts, safer for VRAM/RAM
                preview=False,
                device="gpu",
                verbose=True,
            )
            return  # success on GPU
        except Exception as e:
            gpu_error_msg = str(e)
            # Log GPU error in status text only, not as fatal error
            update_job_status(
                case_id,
                "GPU failed (likely low VRAM). Falling back to CPU...",
            )

    # ----------------- Fall back to CPU -----------------
    update_job_status(
        case_id,
        "Running lung segmentation on CPU (this may take 10–30 minutes)..."
    )

    try:
        totalsegmentator(
            input=input_nii,
            output=case_result_dir,
            task="total",
            roi_subset=LUNG_LOBE_CLASSES,
            fast=True,
            body_seg=True,
            force_split=True,
            preview=False,
            device="cpu",
            verbose=True,
        )
        # success on CPU, make sure no error is stored
        update_job_status(case_id, "Lung segmentation on CPU completed.")
    except Exception as cpu_err:
        # If CPU also fails, now it's a real error
        combined_msg = f"GPU error: {gpu_error_msg}; CPU error: {cpu_err}" if gpu_error_msg else str(cpu_err)
        raise RuntimeError(combined_msg)


def process_case(case_id: str, uploaded_path: str, original_filename: str):
    """
    Background worker:
    - convert input to NIfTI if needed
    - run TotalSegmentator (lung-only, GPU first → CPU fallback)
    - convert lung masks to NRRD
    - create ZIP file
    - update JOBS with status + zip_path
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"totalseg_{case_id}_")
    case_result_dir = os.path.join(RESULT_BASE_DIR, case_id)
    os.makedirs(case_result_dir, exist_ok=True)

    try:
        update_job_status(case_id, "Preparing input...")

        filename_lower = original_filename.lower()

        # -------------------------------------------------
        # 1. Convert input to NIfTI (.nii / .nii.gz)
        # -------------------------------------------------
        if filename_lower.endswith((".nii", ".nii.gz")):
            input_nii = uploaded_path

        elif filename_lower.endswith(".nrrd"):
            update_job_status(case_id, "Converting NRRD to NIfTI...")
            input_nii = convert_nrrd_to_nifti(uploaded_path, tmp_dir)

        elif filename_lower.endswith(".zip"):
            # DICOM ZIP -> NIfTI
            update_job_status(case_id, "Extracting DICOM ZIP and converting to NIfTI...")

            dicom_dir = os.path.join(tmp_dir, "dicom")
            os.makedirs(dicom_dir, exist_ok=True)
            with zipfile.ZipFile(uploaded_path, "r") as zip_ref:
                zip_ref.extractall(dicom_dir)

            nifti_dir = os.path.join(tmp_dir, "nifti")
            os.makedirs(nifti_dir, exist_ok=True)

            dicom2nifti.convert_directory(dicom_dir, nifti_dir, reorient=True)

            nii_files = [
                f for f in os.listdir(nifti_dir)
                if f.endswith(".nii.gz") or f.endswith(".nii")
            ]
            if not nii_files:
                raise RuntimeError("DICOM to NIfTI conversion failed: no NIfTI files found.")

            input_nii = os.path.join(nifti_dir, nii_files[0])

        else:
            raise RuntimeError(
                "Unsupported file type. Please upload NIfTI (.nii / .nii.gz), "
                "NRRD (.nrrd) or DICOM ZIP (.zip)."
            )

        # -------------------------------------------------
        # 2. Run TotalSegmentator (lung-only, GPU→CPU)
        # -------------------------------------------------
        run_totalseg_lung(input_nii, case_result_dir, case_id)

        # -------------------------------------------------
        # 3. Convert lung masks to NRRD
        # -------------------------------------------------
        update_job_status(case_id, "Converting lung masks to NRRD...")

        nrrd_dir = os.path.join(case_result_dir, "nrrd_masks")
        os.makedirs(nrrd_dir, exist_ok=True)

        for root, _, files in os.walk(case_result_dir):
            for f in files:
                # only convert the lung masks
                if not (f.endswith(".nii") or f.endswith(".nii.gz")):
                    continue

                base = os.path.basename(f)
                # TotalSegmentator lung files start with "lung_..."
                if not base.startswith("lung_"):
                    continue

                nii_file = os.path.join(root, f)
                convert_nii_to_nrrd(nii_file, nrrd_dir)

        # -------------------------------------------------
        # 4. Create ZIP with NRRD masks
        # -------------------------------------------------
        update_job_status(case_id, "Creating ZIP file...")

        zip_name = f"{case_id}_lungs_nrrd.zip"
        zip_path = os.path.join(case_result_dir, zip_name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for f in os.listdir(nrrd_dir):
                file_path = os.path.join(nrrd_dir, f)
                zipf.write(file_path, arcname=f)

        if not os.path.exists(zip_path):
            raise RuntimeError("ZIP file creation failed.")

        with JOBS_LOCK:
            JOBS[case_id]["zip_path"] = zip_path

        update_job_status(case_id, "finished")

    except Exception as e:
        # Real failure (CPU also failed or pre/post steps crashed)
        update_job_status(case_id, "error", str(e))
    finally:
        # Clean up temporary directory; keep case_result_dir for the ZIP
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------
@app.route("/api/totalseg_start", methods=["POST"])
def totalseg_start():
    """
    Start a new lung segmentation job.
    Request: multipart/form-data with "file"
    Response: { "case_id": "...", "status": "started" }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    case_id = str(uuid.uuid4())[:8]
    original_name = file.filename

    case_upload_dir = os.path.join(UPLOAD_DIR, case_id)
    os.makedirs(case_upload_dir, exist_ok=True)

    uploaded_path = os.path.join(case_upload_dir, original_name)
    file.save(uploaded_path)

    with JOBS_LOCK:
        JOBS[case_id] = {
            "status": "started",
            "error": None,
            "zip_path": None,
            "original_name": original_name,
        }

    # Start background worker thread
    worker = threading.Thread(
        target=process_case,
        args=(case_id, uploaded_path, original_name),
        daemon=True,
    )
    worker.start()

    return jsonify({"case_id": case_id, "status": "started"}), 200


@app.route("/api/totalseg_status/<case_id>", methods=["GET"])
def totalseg_status(case_id):
    """
    Get status of a lung segmentation job.
    Response: { "case_id": "...", "status": "...", "error": "..." }
    """
    with JOBS_LOCK:
        job = JOBS.get(case_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "case_id": case_id,
        "status": job.get("status"),
        "error": job.get("error"),
    })


@app.route("/api/totalseg_download/<case_id>", methods=["GET"])
def totalseg_download(case_id):
    """
    Download the ZIP of lung NRRD masks for a finished job.
    """
    with JOBS_LOCK:
        job = JOBS.get(case_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.get("status") != "finished":
        return jsonify({"error": "Job not finished yet"}), 400

    zip_path = job.get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"error": "ZIP file not found"}), 500

    base_name = job.get("original_name", case_id).rsplit(".", 1)[0]
    download_name = f"{base_name}_lungs_nrrd.zip"
    return send_file(zip_path, as_attachment=True, download_name=download_name)


if __name__ == "__main__":
    # Make sure only one server uses port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
