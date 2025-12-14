#3D slicer code:(app.py)
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import io
import base64

import numpy as np
import SimpleITK as sitk
import pydicom
from skimage import measure
from PIL import Image

# Try nibabel for NIfTI
try:
    import nibabel as nib
    HAVE_NIB = True
except Exception:
    HAVE_NIB = False


# ------------------------------------------------------
#  FLASK APP
# ------------------------------------------------------
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "/mnt/external/Testing project/pythonProject2/upload"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ------------------------------------------------------
#  GLOBAL CORS
# ------------------------------------------------------
@app.after_request
def apply_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


# ------------------------------------------------------
#  BASIC UTILITIES
# ------------------------------------------------------
def window_image(img, ww=400, wl=40):
    """Apply CT windowing and return 8-bit image."""
    img = img.astype(np.float32)
    low = wl - ww / 2.0
    high = wl + ww / 2.0
    img = np.clip(img, low, high)
    img = (img - low) / (high - low + 1e-6)
    img = (img * 255.0).astype(np.uint8)
    return img


def slice_to_png_base64(slice_2d, ww=400, wl=40):
    """Grayscale CT slice → PNG (base64)."""
    arr = window_image(slice_2d, ww, wl)
    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def mask_to_overlay_png_base64(mask_2d):
    """
    Binary mask → transparent green PNG (base64).
    """
    mask = (mask_2d > 0).astype(np.uint8)
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[mask > 0, 1] = 255     # green
    rgba[mask > 0, 3] = 160     # alpha
    pil_img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ------------------------------------------------------
#  LOADERS
# ------------------------------------------------------
def load_dicom_series(folder):
    reader = sitk.ImageSeriesReader()
    files = reader.GetGDCMSeriesFileNames(folder)
    if len(files) == 0:
        raise ValueError(f"No DICOM series found in: {folder}")
    reader.SetFileNames(files)
    img = reader.Execute()
    vol = sitk.GetArrayFromImage(img)         # (z, y, x)
    return vol.astype(np.float32)


def load_ct_volume(path):
    """
    Load CT volume from folder/file (.npy / .nii(.gz) / .nrrd / .dcm).
    Returns (D, H, W).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"CT path does not exist: {path}")

    if os.path.isdir(path):
        files = os.listdir(path)
        npy_files = [f for f in files if f.lower().endswith(".npy")]
        nii_files = [f for f in files if f.lower().endswith((".nii", ".nii.gz"))]
        nrrd_files = [f for f in files if f.lower().endswith(".nrrd")]
        dcm_files = [f for f in files if f.lower().endswith(".dcm")]

        if npy_files:
            vol = np.load(os.path.join(path, npy_files[0]))
            return vol.astype(np.float32)

        if nii_files and HAVE_NIB:
            img = nib.load(os.path.join(path, nii_files[0]))
            vol = img.get_fdata()
            return vol.astype(np.float32)

        if nrrd_files:
            img = sitk.ReadImage(os.path.join(path, nrrd_files[0]))
            vol = sitk.GetArrayFromImage(img)
            return vol.astype(np.float32)

        if dcm_files:
            return load_dicom_series(path)

        raise ValueError("No CT volume found in folder.")

    # single file
    low = path.lower()
    if low.endswith(".npy"):
        return np.load(path).astype(np.float32)

    if low.endswith((".nii", ".nii.gz")) and HAVE_NIB:
        img = nib.load(path)
        return img.get_fdata().astype(np.float32)

    if low.endswith(".nrrd"):
        img = sitk.ReadImage(path)
        return sitk.GetArrayFromImage(img).astype(np.float32)

    if low.endswith(".dcm"):
        ds = pydicom.dcmread(path)
        arr = ds.pixel_array.astype(np.float32)
        slope = getattr(ds, "RescaleSlope", 1)
        intercept = getattr(ds, "RescaleIntercept", 0)
        vol = arr * slope + intercept
        return vol[np.newaxis, ...]

    raise ValueError("Unsupported CT format.")


def load_seg_volume(path):
    """
    Load segmentation (.npy / .nii(.gz) / .nrrd / .dcm, file or folder).
    Returns binary mask (D, H, W) in {0,1}.
    Supports DICOM-SEG via SimpleITK, merging all labels if 4D.
    """
    if not path:
        raise ValueError("Empty segmentation path.")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Segmentation path does not exist: {path}")

    seg = None

    # ----- Folder -----
    if os.path.isdir(path):
        files = os.listdir(path)
        npy_files = [f for f in files if f.lower().endswith(".npy")]
        nii_files = [f for f in files if f.lower().endswith((".nii", ".nii.gz"))]
        nrrd_files = [f for f in files if f.lower().endswith(".nrrd")]
        dcm_files = [f for f in files if f.lower().endswith(".dcm")]

        if npy_files:
            seg = np.load(os.path.join(path, npy_files[0]))
        elif nii_files and HAVE_NIB:
            img = nib.load(os.path.join(path, nii_files[0]))
            seg = img.get_fdata()
        elif nrrd_files:
            img = sitk.ReadImage(os.path.join(path, nrrd_files[0]))
            seg = sitk.GetArrayFromImage(img)
        elif dcm_files:
            # Take first DICOM-SEG object in folder
            seg_img = sitk.ReadImage(os.path.join(path, dcm_files[0]))
            seg = sitk.GetArrayFromImage(seg_img)
        else:
            raise ValueError("No segmentation file in folder.")

    # ----- Single file -----
    else:
        low = path.lower()
        if low.endswith(".npy"):
            seg = np.load(path)
        elif low.endswith((".nii", ".nii.gz")) and HAVE_NIB:
            img = nib.load(path)
            seg = img.get_fdata()
        elif low.endswith(".nrrd"):
            img = sitk.ReadImage(path)
            seg = sitk.GetArrayFromImage(img)
        elif low.endswith(".dcm"):
            # DICOM-SEG: SimpleITK will read as image (possibly 4D)
            seg_img = sitk.ReadImage(path)
            seg = sitk.GetArrayFromImage(seg_img)
        else:
            raise ValueError("Unsupported segmentation format.")

    # ----- Convert to binary mask, handle 4D SEG -----
    seg = np.asarray(seg)

    # If 4D (num_labels, z, y, x) -> merge labels into one mask
    if seg.ndim == 4:
        seg = (seg > 0).any(axis=0).astype(np.uint8)
    else:
        seg = (seg > 0).astype(np.uint8)

    return seg


# ------------------------------------------------------
#  VIEWER: INIT (2D + optional overlays)
# ------------------------------------------------------
@app.route("/viewer/init", methods=["POST"])
def viewer_init():
    try:
        data = request.get_json()
        ct_path = data["path"]
        seg_path = data.get("seg_path", "").strip()
        ww = data.get("ww", 400)
        wl = data.get("wl", 40)

        vol = load_ct_volume(ct_path)
        D, H, W = vol.shape
        mid = {"z": D // 2, "y": H // 2, "x": W // 2}

        # CT slices (NO rotation; we rotate sagittal/coronal in frontend)
        axial_slice = vol[mid["z"], :, :]
        sag_slice = vol[:, :, mid["x"]]      # (D, H)
        cor_slice = vol[:, mid["y"], :]      # (D, W)

        axial_b64 = slice_to_png_base64(axial_slice, ww, wl)
        sagittal_b64 = slice_to_png_base64(sag_slice, ww, wl)
        coronal_b64 = slice_to_png_base64(cor_slice, ww, wl)

        axial_seg_b64 = None
        sagittal_seg_b64 = None
        coronal_seg_b64 = None

        if seg_path:
            seg = load_seg_volume(seg_path)
            if seg.shape != vol.shape:
                raise ValueError(f"Segmentation shape {seg.shape} does not match CT {vol.shape}")

            axial_mask = seg[mid["z"], :, :]
            sag_mask = seg[:, :, mid["x"]]
            cor_mask = seg[:, mid["y"], :]

            axial_seg_b64 = mask_to_overlay_png_base64(axial_mask)
            sagittal_seg_b64 = mask_to_overlay_png_base64(sag_mask)
            coronal_seg_b64 = mask_to_overlay_png_base64(cor_mask)

        return jsonify({
            "shape": {"depth": D, "height": H, "width": W},
            "mid_indices": mid,
            "axial_png": axial_b64,
            "sagittal_png": sagittal_b64,
            "coronal_png": coronal_b64,
            "axial_seg_png": axial_seg_b64,
            "sagittal_seg_png": sagittal_seg_b64,
            "coronal_seg_png": coronal_seg_b64
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------
#  VIEWER: SLICE
# ------------------------------------------------------
@app.route("/viewer/slice", methods=["POST"])
def viewer_slice():
    try:
        data = request.get_json()
        ct_path = data["path"]
        seg_path = data.get("seg_path", "").strip()
        axis = data["axis"]
        index = int(data["index"])
        ww = data.get("ww", 400)
        wl = data.get("wl", 40)

        vol = load_ct_volume(ct_path)
        D, H, W = vol.shape

        if axis == "axial":
            index = max(0, min(D - 1, index))
            ct_slice = vol[index, :, :]

        elif axis == "sagittal":
            index = max(0, min(W - 1, index))
            ct_slice = vol[:, :, index]

        elif axis == "coronal":
            index = max(0, min(H - 1, index))
            ct_slice = vol[:, index, :]

        else:
            return jsonify({"error": "Invalid axis"}), 400

        ct_b64 = slice_to_png_base64(ct_slice, ww, wl)

        seg_b64 = None
        if seg_path:
            seg = load_seg_volume(seg_path)
            if seg.shape != vol.shape:
                raise ValueError(f"Segmentation shape {seg.shape} does not match CT {vol.shape}")

            if axis == "axial":
                mask_slice = seg[index, :, :]
            elif axis == "sagittal":
                mask_slice = seg[:, :, index]
            else:
                mask_slice = seg[:, index, :]

            seg_b64 = mask_to_overlay_png_base64(mask_slice)

        return jsonify({"png_ct": ct_b64, "png_seg": seg_b64})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------
#  3D SEGMENTATION MESH
# ------------------------------------------------------
@app.route("/viewer/seg3d", methods=["POST"])
def viewer_seg3d():
    try:
        data = request.get_json()
        seg_path = data["seg_path"]

        seg = load_seg_volume(seg_path)
        if seg.max() == 0:
            return jsonify({"error": "Segmentation is empty (all zeros)."}), 400

        verts, faces, normals, values = measure.marching_cubes(seg, level=0.5)
        if verts.shape[0] == 0:
            return jsonify({"error": "Marching cubes produced no vertices."}), 400

        return jsonify({
            "vertices": verts.tolist(),
            "faces": faces.tolist()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------
#  UPLOAD & LIST
# ------------------------------------------------------
@app.route("/upload-folder", methods=["POST"])
def upload_folder():
    if "files" not in request.files:
        return jsonify({"error": "No files sent"}), 400

    files = request.files.getlist("files")
    stored = []

    for f in files:
        save_path = os.path.join(UPLOAD_FOLDER, f.filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        f.save(save_path)
        stored.append(save_path)

    return jsonify({"message": f"Uploaded {len(stored)} files"})


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    save_path = os.path.join(UPLOAD_FOLDER, f.filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    f.save(save_path)
    return jsonify({"message": "File uploaded"})


@app.route("/list-items", methods=["GET"])
def list_items():
    items = []
    for root, dirs, files in os.walk(UPLOAD_FOLDER):
        for d in dirs:
            items.append({"path": os.path.join(root, d), "type": "folder"})
        for f in files:
            items.append({"path": os.path.join(root, f), "type": "file"})
    return jsonify({"items": items})


# ------------------------------------------------------
#  RUN
# ------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
