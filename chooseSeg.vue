// this is for segmentation, it requires app1.*py

<template>
  <div>
    <h3>Lung Segmentation (TotalSegmentator)</h3>

    <p>
      Supported formats:
      <strong>.nii, .nii.gz, .nrrd, .zip (DICOM)</strong>
    </p>

    <input type="file" @change="onFileChange" />

    <button
      @click="startSegmentation"
      :disabled="!file || loading"
    >
      {{ loading ? "Processing..." : "Start Lung Segmentation" }}
    </button>

    <div v-if="caseId" style="margin-top: 1rem;">
      <p><strong>Job ID:</strong> {{ caseId }}</p>
    </div>

    <div v-if="statusText" style="margin-top: 0.5rem;">
      <p><strong>Status:</strong> {{ statusText }}</p>
    </div>

    <div v-if="errorText" style="margin-top: 0.5rem; color: red;">
      <p><strong>Error:</strong> {{ errorText }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from "vue";
import axios from "axios";

const file = ref(null);
const loading = ref(false);
const statusText = ref("");
const errorText = ref("");
const caseId = ref("");
let pollTimer = null;

const API_BASE = "http://localhost:5000"; // change if needed

const onFileChange = (e) => {
  file.value = e.target.files[0] || null;
  statusText.value = "";
  errorText.value = "";
  caseId.value = "";
};

const startSegmentation = async () => {
  if (!file.value) return;

  loading.value = true;
  statusText.value = "Uploading file and starting lung segmentation job...";
  errorText.value = "";
  caseId.value = "";

  // Clear previous polling if any
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }

  try {
    // 1) Start job
    const formData = new FormData();
    formData.append("file", file.value);

    const startRes = await axios.post(`${API_BASE}/api/totalseg_start`, formData);
    caseId.value = startRes.data.case_id || "";
    statusText.value = "Job started. Waiting for status updates...";

    if (!caseId.value) {
      throw new Error("No case_id returned from backend.");
    }

    // 2) Poll job status every 3 seconds
    pollTimer = setInterval(checkStatus, 3000);
  } catch (err) {
    console.error(err);
    errorText.value = "Failed to start lung segmentation: " + (err.message || "Unknown error");
    statusText.value = "";
    loading.value = false;
  }
};

const checkStatus = async () => {
  if (!caseId.value) return;

  try {
    const res = await axios.get(`${API_BASE}/api/totalseg_status/${caseId.value}`);
    const status = res.data.status;
    const error = res.data.error;

    if (error) {
      statusText.value = "Job failed.";
      errorText.value = error;
      stopPolling();
      loading.value = false;
      return;
    }

    if (status === "finished") {
      statusText.value = "Lung segmentation finished. Downloading result ZIP...";
      await downloadResult();
      stopPolling();
      loading.value = false;
    } else {
      // status examples:
      // "Preparing input...", "Converting NRRD to NIfTI...",
      // "Running lung segmentation on GPU ...",
      // "GPU run failed, switching to CPU ...",
      // "Converting lung masks to NRRD...", "Creating ZIP file...", etc.
      statusText.value = status;
    }
  } catch (err) {
    console.error(err);
    errorText.value = "Error while checking status: " + (err.message || "Unknown error");
    stopPolling();
    loading.value = false;
  }
};

const downloadResult = async () => {
  if (!caseId.value) return;

  try {
    const res = await axios.get(
      `${API_BASE}/api/totalseg_download/${caseId.value}`,
      { responseType: "blob" }
    );

    const blob = new Blob([res.data]);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    // Match backend naming: *_lungs_nrrd.zip
    const baseName = (file.value?.name || "result").replace(/\..+$/, "");
    link.download = `${baseName}_lungs_nrrd.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    statusText.value = "Download started.";
  } catch (err) {
    console.error(err);
    errorText.value = "Failed to download result: " + (err.message || "Unknown error");
  }
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

onBeforeUnmount(() => {
  stopPolling();
});
</script>

::contentReference[oaicite:0]{index=0}
