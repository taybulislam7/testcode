<template>
  <div class="card-wrapper">
  <div class="conversion-card">
    <h1 class="title">Medical Image Format Conversion</h1>
    <p class="subtitle">
      Select an uploaded file or folder, choose a target format, and convert it on the server.
    </p>

    <div class="top-bar">
      <button class="refresh-btn" @click="fetchItems" :disabled="isLoadingList">
        <span v-if="isLoadingList">⏳ Refreshing...</span>
        <span v-else>🔄 Refresh List</span>
      </button>
      <span class="small-info">Make sure you’ve uploaded data first.</span>
    </div>

    <div class="field-group">
      <label class="field-label">Source Item</label>

      <div v-if="items.length" class="select-wrapper">
        <select v-model="selectedPath" class="select-input">
          <option
            v-for="item in items"
            :key="item.path"
            :value="item.path"
          >
            {{ item.type === 'folder' ? '[Folder] ' : '[File] ' }}{{ item.path }}
          </option>
        </select>
      </div>

      <p v-else class="empty-text">
        No files or folders available. Please upload them on the upload page first.
      </p>
    </div>

    <div class="field-group">
      <label class="field-label">Target Format</label>
      <div class="select-wrapper">
        <select v-model="selectedFormat" class="select-input">
          <option value="nii">NIfTI (.nii)</option>
          <option value="nii.gz">NIfTI Compressed (.nii.gz)</option>
          <option value="nrrd">NRRD (.nrrd)</option>
          <option value="png">PNG (.png)</option>
          <option value="jpg">JPEG (.jpg)</option>
        </select>
      </div>
    </div>

    <div class="actions">
      <button
        class="primary-btn"
        @click="convertFormat"
        :disabled="!items.length || isConverting"
      >
        <span v-if="isConverting">⏳ Converting...</span>
        <span v-else>⚙️ Start Conversion</span>
      </button>
    </div>

    <div class="status-area">
      <p
        v-if="convertMessage"
        class="status"
        :class="convertMessage.startsWith('Conversion failed') || convertMessage.startsWith('Failed') ? 'error' : 'success'"
      >
        {{ convertMessage }}
      </p>
    </div>

    <p class="hint">
      For NIfTI/NRRD, select a DICOM folder. For PNG/JPEG, select a single DICOM file.
      The converted file path will be shown after processing.
    </p>
  </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const items = ref([])
const selectedPath = ref('')
const selectedFormat = ref('nii')
const convertMessage = ref('')
const isLoadingList = ref(false)
const isConverting = ref(false)

async function fetchItems() {
  try {
    isLoadingList.value = true
    convertMessage.value = ''
    const res = await axios.get('http://localhost:5000/list-items')
    items.value = Array.isArray(res.data.items) ? res.data.items : []
    selectedPath.value = items.value.length ? items.value[0].path : ''
  } catch (err) {
    items.value = []
    selectedPath.value = ''
    convertMessage.value = 'Failed to fetch list: ' + err.message
  } finally {
    isLoadingList.value = false
  }
}

async function convertFormat() {
  if (!selectedPath.value) {
    convertMessage.value = 'Please select a file or folder first.'
    return
  }
  try {
    isConverting.value = true
    convertMessage.value = ''
    const res = await axios.post('http://localhost:5000/convert', {
      path: selectedPath.value,
      format: selectedFormat.value
    })
    convertMessage.value =
      res.data.message + '\nOutput File Path: ' + (res.data.output_path || 'Unknown')
  } catch (err) {
    convertMessage.value = 'Conversion failed: ' + err.message
  } finally {
    isConverting.value = false
  }
}
</script>

<style scoped>
.conversion-card {
  width: 100%;
  max-width: 560px;
  background: #ffffff;
  border-radius: 18px;
  padding: 28px 28px 22px;
  box-shadow:
    0 18px 45px rgba(15, 23, 42, 0.13),
    0 0 0 1px rgba(148, 163, 184, 0.18);
  box-sizing: border-box;
}

.title {
  font-size: 1.6rem;
  margin: 0 0 6px;
  color: #0f172a;
  letter-spacing: 0.02em;
}

.subtitle {
  margin: 0 0 18px;
  font-size: 0.95rem;
  line-height: 1.5;
  color: #64748b;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.refresh-btn {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid #cbd5f5;
  background: #f8fafc;
  font-size: 0.9rem;
  font-weight: 500;
  color: #0f172a;
  cursor: pointer;
  transition:
    background-color 0.12s ease-out,
    transform 0.08s ease-out,
    box-shadow 0.12s ease-out;
}

.refresh-btn:hover:not(:disabled) {
  background: #e5edff;
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(148, 163, 184, 0.35);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: default;
  box-shadow: none;
  transform: none;
}

.small-info {
  font-size: 0.8rem;
  color: #9ca3af;
}

.field-group {
  margin-bottom: 16px;
}

.field-label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}

.select-wrapper {
  position: relative;
}

.select-input {
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #d4d4dd;
  font-size: 0.9rem;
  color: #0f172a;
  background: #f9fafb;
  outline: none;
  appearance: none;
  box-sizing: border-box;
}

.select-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.25);
  background: #ffffff;
}

.empty-text {
  margin: 4px 0 0;
  font-size: 0.85rem;
  color: #9ca3af;
}

.actions {
  margin-top: 6px;
  margin-bottom: 8px;
}

.primary-btn {
  width: 100%;
  padding: 10px 16px;
  border-radius: 999px;
  border: none;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #ffffff;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.45);
  transition:
    background 0.12s ease-out,
    transform 0.08s ease-out,
    box-shadow 0.12s ease-out,
    opacity 0.12s ease-out;
}

.primary-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8, #1e40af);
  transform: translateY(-1px);
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: default;
  box-shadow: none;
  transform: none;
}

.status-area {
  min-height: 36px;
  display: flex;
  align-items: center;
}

.status {
  margin: 4px 0 0;
  font-size: 0.9rem;
  line-height: 1.4;
  white-space: pre-line;
}

.status.success {
  color: #15803d;
}

.status.error {
  color: #b91c1c;
}

.hint {
  margin-top: 10px;
  font-size: 0.8rem;
  color: #9ca3af;
  border-top: 1px dashed #e5e7eb;
  padding-top: 8px;
}
</style>
