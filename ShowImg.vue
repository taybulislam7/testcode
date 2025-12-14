<template>
  <div class="viewer-page">
    <!-- Header / Source selection -->
    <div class="header-card">
      <h2 class="title">CT + 3D Segmentation Viewer</h2>
      <p class="subtitle">
        Select an uploaded CT folder or file, load the volume to see axial / coronal / sagittal
        slices, and optionally load a 3D segmentation mesh.
      </p>

      <!-- CT SOURCE: dropdown + Upload CT + Refresh -->
      <div class="field-group">
        <label class="field-label">CT Source Path</label>
        <div class="row">
          <select v-model="selectedPath" class="select-input">
            <option disabled value="">-- Select uploaded CT folder/file --</option>
            <option
              v-for="item in items"
              :key="'ct-' + item.path"
              :value="item.path"
            >
              {{ item.type === 'folder' ? '[Folder] ' : '[File] ' }}{{ item.path }}
            </option>
          </select>

          <button class="small-btn" @click="triggerCtFolderSelect">
            Upload CT
          </button>

          <button class="small-btn" @click="fetchItems" :disabled="isLoadingList">
            {{ isLoadingList ? 'Refreshing...' : 'Refresh' }}
          </button>

          <input
            ref="ctFolderInput"
            type="file"
            webkitdirectory
            multiple
            class="hidden-input"
            @change="handleCtFolderSelected"
          />
        </div>
      </div>

      <!-- SEGMENTATION: dropdown + Upload Seg -->
      <div class="field-group">
        <label class="field-label">Segmentation Path (npy / nii.gz / nrrd / folder)</label>
        <div class="row">
          <select v-model="segPath" class="select-input">
            <option value="">-- Optional: select segmentation file/folder --</option>
            <option
              v-for="item in items"
              :key="'seg-' + item.path"
              :value="item.path"
            >
              {{ item.path }}
            </option>
          </select>

          <button class="small-btn" @click="triggerSegFileSelect">
            Upload Seg
          </button>

          <input
            ref="segFileInput"
            type="file"
            class="hidden-input"
            @change="handleSegFileSelected"
          />
        </div>
      </div>

      <div class="row">
        <button class="primary-btn" @click="loadVolume" :disabled="!selectedPath || isLoadingVolume">
          {{ isLoadingVolume ? 'Loading CT Volume...' : 'Load CT Volume' }}
        </button>
        <button class="secondary-btn" @click="loadMesh" :disabled="!segPath || isLoadingMesh">
          {{ isLoadingMesh ? 'Loading 3D Mesh...' : 'Load 3D Mesh' }}
        </button>
      </div>

      <p v-if="statusMessage" class="status-text">
        {{ statusMessage }}
      </p>
    </div>

    <!-- 4-pane layout -->
    <div v-if="shape" class="grid-2x2">
      <!-- Axial -->
      <div class="pane">
        <div class="pane-header">
          <span>Axial (z)</span>
          <span class="index-label">z = {{ axialIndex }} / {{ shape.depth - 1 }}</span>
        </div>

        <!-- ROI control panel (Axial) -->
        <div class="roi-toolbar">
          <button class="roi-btn" @click="undoRoi('axial')" :disabled="!canUndo('axial')">Undo</button>
          <button class="roi-btn" @click="redoRoi('axial')" :disabled="!canRedo('axial')">Redo</button>
          <button class="roi-btn" @click="clearRois('axial')" :disabled="!hasRois('axial')">Clear</button>
          <button class="roi-btn primary" @click="saveViewAsPng('axial')" :disabled="!axialImg">Save PNG</button>
        </div>

        <div class="slice-frame" ref="axialFrame">
          <img
            v-if="axialImg"
            :src="axialImg"
            class="slice-img"
            :style="{ transform: 'scale(' + zoomAxial + ')' }"
          />
          <img
            v-if="axialSegImg"
            :src="axialSegImg"
            class="slice-img overlay"
            :style="{ transform: 'scale(' + zoomAxial + ')' }"
          />
          <canvas
            ref="axialCanvas"
            class="roi-canvas"
            @mousedown="onRoiMouseDown('axial', $event)"
            @mousemove="onRoiMouseMove($event)"
            @mouseup="onRoiMouseUp"
            @mouseleave="onRoiMouseUp"
          ></canvas>
        </div>

        <div class="slider-row">
          <label class="slider-label">Axial (z)</label>
          <input
            type="range"
            :min="0"
            :max="shape.depth - 1"
            v-model.number="axialIndex"
            @input="onAxialChange"
          />
        </div>
        <div class="slider-row">
          <label class="slider-label">Zoom</label>
          <input
            type="range"
            min="0.4"
            max="2"
            step="0.01"
            v-model.number="zoomAxial"
          />
        </div>
      </div>

      <!-- Sagittal -->
      <div class="pane">
        <div class="pane-header">
          <span>Sagittal (x)</span>
          <span class="index-label">x = {{ sagittalIndex }} / {{ shape.width - 1 }}</span>
        </div>

        <!-- ROI control panel (Sagittal) -->
        <div class="roi-toolbar">
          <button class="roi-btn" @click="undoRoi('sagittal')" :disabled="!canUndo('sagittal')">Undo</button>
          <button class="roi-btn" @click="redoRoi('sagittal')" :disabled="!canRedo('sagittal')">Redo</button>
          <button class="roi-btn" @click="clearRois('sagittal')" :disabled="!hasRois('sagittal')">Clear</button>
          <button class="roi-btn primary" @click="saveViewAsPng('sagittal')" :disabled="!sagittalImg">Save PNG</button>
        </div>

        <div class="slice-frame" ref="sagittalFrame">
          <img
            v-if="sagittalImg"
            :src="sagittalImg"
            class="slice-img sagittal-img"
            :style="{ transform: 'translate(-50%, -50%) scaleY(-1) scale(' + zoomSagittal + ')' }"
          />
          <img
            v-if="sagittalSegImg"
            :src="sagittalSegImg"
            class="slice-img overlay sagittal-img"
            :style="{ transform: 'translate(-50%, -50%) scaleY(-1) scale(' + zoomSagittal + ')' }"
          />
          <canvas
            ref="sagittalCanvas"
            class="roi-canvas"
            @mousedown="onRoiMouseDown('sagittal', $event)"
            @mousemove="onRoiMouseMove($event)"
            @mouseup="onRoiMouseUp"
            @mouseleave="onRoiMouseUp"
          ></canvas>
        </div>

        <div class="slider-row">
          <label class="slider-label">Sagittal (x)</label>
          <input
            type="range"
            :min="0"
            :max="shape.width - 1"
            v-model.number="sagittalIndex"
            @input="onSagittalChange"
          />
        </div>
        <div class="slider-row">
          <label class="slider-label">Zoom</label>
          <input
            type="range"
            min="0.4"
            max="2"
            step="0.01"
            v-model.number="zoomSagittal"
          />
        </div>
      </div>

      <!-- Coronal -->
      <div class="pane">
        <div class="pane-header">
          <span>Coronal (y)</span>
          <span class="index-label">y = {{ coronalIndex }} / {{ shape.height - 1 }}</span>
        </div>

        <!-- ROI control panel (Coronal) -->
        <div class="roi-toolbar">
          <button class="roi-btn" @click="undoRoi('coronal')" :disabled="!canUndo('coronal')">Undo</button>
          <button class="roi-btn" @click="redoRoi('coronal')" :disabled="!canRedo('coronal')">Redo</button>
          <button class="roi-btn" @click="clearRois('coronal')" :disabled="!hasRois('coronal')">Clear</button>
          <button class="roi-btn primary" @click="saveViewAsPng('coronal')" :disabled="!coronalImg">Save PNG</button>
        </div>

        <div class="slice-frame" ref="coronalFrame">
          <img
            v-if="coronalImg"
            :src="coronalImg"
            class="slice-img coronal-img"
            :style="{ transform: 'translate(-50%, -50%) scaleY(-1) scale(' + zoomCoronal + ')' }"
          />
          <img
            v-if="coronalSegImg"
            :src="coronalSegImg"
            class="slice-img overlay coronal-img"
            :style="{ transform: 'translate(-50%, -50%) scaleY(-1) scale(' + zoomCoronal + ')' }"
          />
          <canvas
            ref="coronalCanvas"
            class="roi-canvas"
            @mousedown="onRoiMouseDown('coronal', $event)"
            @mousemove="onRoiMouseMove($event)"
            @mouseup="onRoiMouseUp"
            @mouseleave="onRoiMouseUp"
          ></canvas>
        </div>

        <div class="slider-row">
          <label class="slider-label">Coronal (y)</label>
          <input
            type="range"
            :min="0"
            :max="shape.height - 1"
            v-model.number="coronalIndex"
            @input="onCoronalChange"
          />
        </div>
        <div class="slider-row">
          <label class="slider-label">Zoom</label>
          <input
            type="range"
            min="0.4"
            max="2"
            step="0.01"
            v-model.number="zoomCoronal"
          />
        </div>
      </div>

      <!-- 3D -->
      <div class="pane">
        <div class="pane-header">
          <span>3D Segmentation</span>
          <span class="index-label">Rotate with mouse, scroll to zoom</span>
        </div>
        <div ref="threeContainer" class="three-container"></div>
      </div>
    </div>

    <p v-else class="empty-hint">
      Load a CT volume to see slices and 3D segmentation.
    </p>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

/* ---------------- Basic state ---------------- */

const items = ref([])
const selectedPath = ref('')
const segPath = ref('')

const isLoadingList = ref(false)
const isLoadingVolume = ref(false)
const isLoadingMesh = ref(false)
const statusMessage = ref('')

const shape = ref(null)

const axialIndex = ref(0)
const sagittalIndex = ref(0)
const coronalIndex = ref(0)

const zoomAxial = ref(1)
const zoomSagittal = ref(1)
const zoomCoronal = ref(1)

const axialImg = ref(null)
const sagittalImg = ref(null)
const coronalImg = ref(null)

const axialSegImg = ref(null)
const sagittalSegImg = ref(null)
const coronalSegImg = ref(null)

/* ---------------- Upload refs ---------------- */

const ctFolderInput = ref(null)
const segFileInput = ref(null)

function triggerCtFolderSelect() {
  ctFolderInput.value && ctFolderInput.value.click()
}
function triggerSegFileSelect() {
  segFileInput.value && segFileInput.value.click()
}

async function handleCtFolderSelected(e) {
  const files = e.target.files
  if (!files || !files.length) return
  try {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    await axios.post('http://localhost:5000/upload-folder', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    statusMessage.value = 'CT folder uploaded.'
    await fetchItems()
  } catch (err) {
    console.error(err)
    statusMessage.value = 'Failed to upload CT folder: ' + err.message
  } finally {
    e.target.value = ''
  }
}

async function handleSegFileSelected(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  try {
    const form = new FormData()
    form.append('file', file)
    await axios.post('http://localhost:5000/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    statusMessage.value = 'Segmentation file uploaded.'
    await fetchItems()
  } catch (err) {
    console.error(err)
    statusMessage.value = 'Failed to upload segmentation file: ' + err.message
  } finally {
    e.target.value = ''
  }
}

/* ---------------- 3D state ---------------- */

const threeContainer = ref(null)
let scene = null
let camera = null
let renderer = null
let mesh = null
let controls = null
let animationId = null

// CT planes in 3D
let axialPlane = null
let sagittalPlane = null
let coronalPlane = null

let axialTex = null
let sagittalTex = null
let coronalTex = null

const axialTexCanvas = document.createElement('canvas')
const sagittalTexCanvas = document.createElement('canvas')
const coronalTexCanvas = document.createElement('canvas')

// TRUE clipping planes
const clipAxial = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0)
const clipCoronal = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0)
const clipSagittal = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0)

/* ---------------- ROI state ---------------- */

const axialCanvas = ref(null)
const sagittalCanvas = ref(null)
const coronalCanvas = ref(null)

const axialFrame = ref(null)
const sagittalFrame = ref(null)
const coronalFrame = ref(null)

const axialRois = ref([])
const sagittalRois = ref([])
const coronalRois = ref([])

// Undo/Redo stacks (per view)
const axialRedo = ref([])
const sagittalRedo = ref([])
const coronalRedo = ref([])

const isDrawing = ref(false)
const currentRoi = ref([])
const activeView = ref(null)

/* ---------------- helpers ---------------- */

function b64ToDataUrl(b64) {
  if (!b64) return null
  return 'data:image/png;base64,' + b64
}

function loadImageDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    if (!dataUrl) return resolve(null)
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = dataUrl
  })
}

function getVolumeCenters() {
  if (!shape.value) return { cx: 0, cy: 0, cz: 0, W: 0, H: 0, D: 0 }
  const D = shape.value.depth
  const H = shape.value.height
  const W = shape.value.width
  const cx = (W - 1) / 2
  const cy = (H - 1) / 2
  const cz = (D - 1) / 2
  return { cx, cy, cz, W, H, D }
}

function updateMeshClippingPlanes() {
  if (!shape.value || !mesh) return
  const { cx, cy, cz } = getVolumeCenters()
  clipAxial.constant = axialIndex.value - cz
  clipCoronal.constant = coronalIndex.value - cy
  clipSagittal.constant = sagittalIndex.value - cx
  mesh.material.needsUpdate = true
}

/**
 * 3D planes show ONLY CT (no seg drawn)
 */
async function updatePlaneTexture(axis, ctDataUrl) {
  const canvas =
    axis === 'axial' ? axialTexCanvas :
    axis === 'sagittal' ? sagittalTexCanvas :
    coronalTexCanvas

  const tex =
    axis === 'axial' ? axialTex :
    axis === 'sagittal' ? sagittalTex :
    coronalTex

  if (!tex) return

  const flipYForView = (axis === 'sagittal' || axis === 'coronal')

  const ctImg = await loadImageDataUrl(ctDataUrl)
  if (!ctImg) return

  canvas.width = ctImg.naturalWidth || ctImg.width
  canvas.height = ctImg.naturalHeight || ctImg.height

  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  if (flipYForView) {
    ctx.save()
    ctx.translate(0, canvas.height)
    ctx.scale(1, -1)
    ctx.drawImage(ctImg, 0, 0, canvas.width, canvas.height)
    ctx.restore()
  } else {
    ctx.drawImage(ctImg, 0, 0, canvas.width, canvas.height)
  }

  tex.needsUpdate = true
}

function updatePlanePosition(axis, index) {
  if (!shape.value) return
  const { cx, cy, cz } = getVolumeCenters()

  if (axis === 'axial' && axialPlane) axialPlane.position.set(0, 0, index - cz)
  if (axis === 'coronal' && coronalPlane) coronalPlane.position.set(0, index - cy, 0)
  if (axis === 'sagittal' && sagittalPlane) sagittalPlane.position.set(index - cx, 0, 0)
}

function disposePlane(p) {
  if (!p) return
  if (p.geometry) p.geometry.dispose()
  if (p.material && p.material.map) p.material.map.dispose()
  if (p.material) p.material.dispose()
}

function rebuildSlicePlanes() {
  if (!scene || !shape.value) return

  if (axialPlane) { scene.remove(axialPlane); disposePlane(axialPlane) }
  if (coronalPlane) { scene.remove(coronalPlane); disposePlane(coronalPlane) }
  if (sagittalPlane) { scene.remove(sagittalPlane); disposePlane(sagittalPlane) }

  axialPlane = coronalPlane = sagittalPlane = null

  const { W, H, D } = getVolumeCenters()

  axialTex = new THREE.CanvasTexture(axialTexCanvas)
  sagittalTex = new THREE.CanvasTexture(sagittalTexCanvas)
  coronalTex = new THREE.CanvasTexture(coronalTexCanvas)

  for (const t of [axialTex, sagittalTex, coronalTex]) {
    t.minFilter = THREE.LinearFilter
    t.magFilter = THREE.LinearFilter
    t.generateMipmaps = false
  }

  const matCommon = (tex) => new THREE.MeshBasicMaterial({
    map: tex,
    transparent: true,
    opacity: 0.30,
    depthWrite: false,
    depthTest: true,
    side: THREE.DoubleSide
  })

  axialPlane = new THREE.Mesh(new THREE.PlaneGeometry(W, H), matCommon(axialTex))
  axialPlane.renderOrder = 2
  scene.add(axialPlane)

  coronalPlane = new THREE.Mesh(new THREE.PlaneGeometry(W, D), matCommon(coronalTex))
  coronalPlane.rotation.x = -Math.PI / 2
  coronalPlane.renderOrder = 2
  scene.add(coronalPlane)

  sagittalPlane = new THREE.Mesh(new THREE.PlaneGeometry(D, H), matCommon(sagittalTex))
  sagittalPlane.rotation.y = Math.PI / 2
  sagittalPlane.renderOrder = 2
  scene.add(sagittalPlane)

  updatePlanePosition('axial', axialIndex.value)
  updatePlanePosition('coronal', coronalIndex.value)
  updatePlanePosition('sagittal', sagittalIndex.value)

  updatePlaneTexture('axial', axialImg.value)
  updatePlaneTexture('coronal', coronalImg.value)
  updatePlaneTexture('sagittal', sagittalImg.value)
}

/* ---------------- File list ---------------- */

async function fetchItems() {
  try {
    isLoadingList.value = true
    const res = await axios.get('http://localhost:5000/list-items')
    items.value = Array.isArray(res.data.items) ? res.data.items : []
    if (!selectedPath.value && items.value.length) selectedPath.value = items.value[0].path
  } catch (err) {
    console.error(err)
    statusMessage.value = 'Failed to load list: ' + err.message
  } finally {
    isLoadingList.value = false
  }
}

/* ---------------- Volume loading ---------------- */

async function loadVolume() {
  if (!selectedPath.value) return
  try {
    isLoadingVolume.value = true
    statusMessage.value = ''

    const res = await axios.post('http://localhost:5000/viewer/init', {
      path: selectedPath.value,
      seg_path: segPath.value,
      ww: 400,
      wl: 40
    })
    if (res.data.error) throw new Error(res.data.error)

    shape.value = res.data.shape
    axialIndex.value = res.data.mid_indices.z
    sagittalIndex.value = res.data.mid_indices.x
    coronalIndex.value = res.data.mid_indices.y

    axialImg.value = b64ToDataUrl(res.data.axial_png)
    sagittalImg.value = b64ToDataUrl(res.data.sagittal_png)
    coronalImg.value = b64ToDataUrl(res.data.coronal_png)

    axialSegImg.value = b64ToDataUrl(res.data.axial_seg_png)
    sagittalSegImg.value = b64ToDataUrl(res.data.sagittal_seg_png)
    coronalSegImg.value = b64ToDataUrl(res.data.coronal_seg_png)

    // reset ROI + redo stacks
    axialRois.value = []; sagittalRois.value = []; coronalRois.value = []
    axialRedo.value = []; sagittalRedo.value = []; coronalRedo.value = []

    await nextTick()
    resizeAllRoiCanvases()

    initThreeIfNeeded()
    rebuildSlicePlanes()
    updateMeshClippingPlanes()

    statusMessage.value = 'CT volume loaded.'
  } catch (err) {
    console.error(err)
    statusMessage.value = 'Failed to load CT volume: ' + err.message
  } finally {
    isLoadingVolume.value = false
  }
}

/* ---------------- Slice fetching ---------------- */

async function fetchSlice(axis, index, targetCtRef, targetSegRef) {
  if (!shape.value || !selectedPath.value) return
  try {
    const res = await axios.post('http://localhost:5000/viewer/slice', {
      path: selectedPath.value,
      seg_path: segPath.value,
      axis,
      index,
      ww: 400,
      wl: 40
    })
    if (res.data.error) throw new Error(res.data.error)

    targetCtRef.value = b64ToDataUrl(res.data.png_ct)
    targetSegRef.value = b64ToDataUrl(res.data.png_seg)

    await nextTick()
    resizeAllRoiCanvases()
    redrawRois(axis)

    if (axis === 'axial') {
      updatePlanePosition('axial', index)
      await updatePlaneTexture('axial', axialImg.value)
    } else if (axis === 'sagittal') {
      updatePlanePosition('sagittal', index)
      await updatePlaneTexture('sagittal', sagittalImg.value)
    } else if (axis === 'coronal') {
      updatePlanePosition('coronal', index)
      await updatePlaneTexture('coronal', coronalImg.value)
    }

    updateMeshClippingPlanes()
  } catch (err) {
    console.error(err)
    statusMessage.value = 'Failed to fetch slice: ' + err.message
  }
}

function onAxialChange() { fetchSlice('axial', axialIndex.value, axialImg, axialSegImg) }
function onSagittalChange() { fetchSlice('sagittal', sagittalIndex.value, sagittalImg, sagittalSegImg) }
function onCoronalChange() { fetchSlice('coronal', coronalIndex.value, coronalImg, coronalSegImg) }

/* ---------------- ROI helpers ---------------- */

function getRoisRef(view) {
  if (view === 'axial') return axialRois
  if (view === 'sagittal') return sagittalRois
  return coronalRois
}
function getRedoRef(view) {
  if (view === 'axial') return axialRedo
  if (view === 'sagittal') return sagittalRedo
  return coronalRedo
}
function getCanvasRef(view) {
  if (view === 'axial') return axialCanvas
  if (view === 'sagittal') return sagittalCanvas
  return coronalCanvas
}

function hasRois(view) {
  return (getRoisRef(view).value || []).length > 0
}
function canUndo(view) {
  return (getRoisRef(view).value || []).length > 0
}
function canRedo(view) {
  return (getRedoRef(view).value || []).length > 0
}

function undoRoi(view) {
  const roisRef = getRoisRef(view)
  const redoRef = getRedoRef(view)
  if (!roisRef.value.length) return
  const last = roisRef.value[roisRef.value.length - 1]
  roisRef.value = roisRef.value.slice(0, -1)
  redoRef.value = [...redoRef.value, last]
  redrawRois(view)
}

function redoRoi(view) {
  const roisRef = getRoisRef(view)
  const redoRef = getRedoRef(view)
  if (!redoRef.value.length) return
  const last = redoRef.value[redoRef.value.length - 1]
  redoRef.value = redoRef.value.slice(0, -1)
  roisRef.value = [...roisRef.value, last]
  redrawRois(view)
}

function clearRois(view) {
  const roisRef = getRoisRef(view)
  const redoRef = getRedoRef(view)
  if (!roisRef.value.length) return
  redoRef.value = []
  roisRef.value = []
  redrawRois(view)
}

/**
 * Save PNG = CT + Seg overlay + ROI (exactly what user sees)
 */
async function saveViewAsPng(view) {
  const canvasRef = getCanvasRef(view)
  const canvas = canvasRef.value
  if (!canvas) return

  const w = canvas.width
  const h = canvas.height

  const out = document.createElement('canvas')
  out.width = w
  out.height = h
  const ctx = out.getContext('2d')

  // pick CT + seg + transform rules per view
  let ctUrl = null, segUrl = null, transform = null
  if (view === 'axial') {
    ctUrl = axialImg.value
    segUrl = axialSegImg.value
    transform = (ctx) => {
      // same as img style: scale(zoomAxial) but since we draw to full canvas,
      // we mimic visually by drawing centered scaled image.
      const z = zoomAxial.value
      ctx.translate(w / 2, h / 2)
      ctx.scale(z, z)
      ctx.translate(-w / 2, -h / 2)
    }
  } else if (view === 'sagittal') {
    ctUrl = sagittalImg.value
    segUrl = sagittalSegImg.value
    transform = (ctx) => {
      const z = zoomSagittal.value
      // match: translate(-50%,-50%) scaleY(-1) scale(z) with oversize
      ctx.translate(w / 2, h / 2)
      ctx.scale(z, -z)
      ctx.translate(-w / 2, -h / 2)
    }
  } else {
    ctUrl = coronalImg.value
    segUrl = coronalSegImg.value
    transform = (ctx) => {
      const z = zoomCoronal.value
      ctx.translate(w / 2, h / 2)
      ctx.scale(z, -z)
      ctx.translate(-w / 2, -h / 2)
    }
  }

  const ctImg = await loadImageDataUrl(ctUrl)
  const segImg = await loadImageDataUrl(segUrl)

  ctx.save()
  if (transform) transform(ctx)
  if (ctImg) ctx.drawImage(ctImg, 0, 0, w, h)
  if (segImg) ctx.drawImage(segImg, 0, 0, w, h)
  ctx.restore()

  // draw ROI (already in correct canvas coordinates)
  ctx.drawImage(canvas, 0, 0, w, h)

  const a = document.createElement('a')
  a.href = out.toDataURL('image/png')
  a.download = `${view}_slice.png`
  a.click()
}

/* ---------------- ROI drawing ---------------- */

function getCanvasAndCtx(view) {
  const canvas = getCanvasRef(view).value
  if (!canvas) return { canvas: null, ctx: null }
  return { canvas, ctx: canvas.getContext('2d') }
}

function resizeOneCanvas(canvasRef) {
  const canvas = canvasRef.value
  if (!canvas || !canvas.parentElement) return
  const parent = canvas.parentElement
  canvas.width = parent.clientWidth
  canvas.height = parent.clientHeight
}

function resizeAllRoiCanvases() {
  resizeOneCanvas(axialCanvas)
  resizeOneCanvas(sagittalCanvas)
  resizeOneCanvas(coronalCanvas)
  redrawRois('axial')
  redrawRois('sagittal')
  redrawRois('coronal')
}

function redrawRois(view) {
  const { canvas, ctx } = getCanvasAndCtx(view)
  if (!canvas || !ctx) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const rois = getRoisRef(view).value || []

  ctx.lineWidth = 2
  ctx.strokeStyle = '#22c55e'
  ctx.fillStyle = 'rgba(34,197,94,0.18)'

  for (const path of rois) {
    if (!path || path.length < 2) continue
    ctx.beginPath()
    ctx.moveTo(path[0].x, path[0].y)
    for (let i = 1; i < path.length; i++) ctx.lineTo(path[i].x, path[i].y)
    ctx.closePath()
    ctx.stroke()
    ctx.fill()
  }

  if (isDrawing.value && activeView.value === view && currentRoi.value.length > 1) {
    const path = currentRoi.value
    ctx.beginPath()
    ctx.moveTo(path[0].x, path[0].y)
    for (let i = 1; i < path.length; i++) ctx.lineTo(path[i].x, path[i].y)
    ctx.stroke()
  }
}

function onRoiMouseDown(view, event) {
  if (event.button !== 0) return
  const { canvas } = getCanvasAndCtx(view)
  if (!canvas) return

  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  isDrawing.value = true
  activeView.value = view
  currentRoi.value = [{ x, y }]
  redrawRois(view)
}

function onRoiMouseMove(event) {
  if (!isDrawing.value || !activeView.value) return
  const { canvas } = getCanvasAndCtx(activeView.value)
  if (!canvas) return

  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  currentRoi.value.push({ x, y })
  redrawRois(activeView.value)
}

function onRoiMouseUp() {
  if (!isDrawing.value || !activeView.value) return
  const roisRef = getRoisRef(activeView.value)
  const redoRef = getRedoRef(activeView.value)

  if (currentRoi.value.length > 2) {
    roisRef.value = [...roisRef.value, [...currentRoi.value]]
    // new action invalidates redo
    redoRef.value = []
  }

  isDrawing.value = false
  redrawRois(activeView.value)
  activeView.value = null
  currentRoi.value = []
}

/* ---------------- 3D viewer ---------------- */

function initThreeIfNeeded() {
  if (!threeContainer.value) return
  if (renderer) return

  const container = threeContainer.value
  const { clientWidth, clientHeight } = container

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x020617)

  camera = new THREE.PerspectiveCamera(40, clientWidth / clientHeight, 0.1, 5000)
  camera.position.set(0, 0, 350)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(clientWidth, clientHeight)
  renderer.localClippingEnabled = true
  container.appendChild(renderer.domElement)

  const light1 = new THREE.DirectionalLight(0xffffff, 0.9)
  light1.position.set(1, 1, 1)
  scene.add(light1)

  const light2 = new THREE.AmbientLight(0xffffff, 0.3)
  scene.add(light2)

  const grid = new THREE.GridHelper(240, 12, 0x4b5563, 0x1f2937)
  grid.position.y = -120
  scene.add(grid)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.1

  const animate = () => {
    animationId = requestAnimationFrame(animate)
    if (controls) controls.update()
    renderer.render(scene, camera)
  }
  animate()

  window.addEventListener('resize', onWindowResize)
}

function onWindowResize() {
  resizeAllRoiCanvases()
  if (!renderer || !camera || !threeContainer.value) return
  const container = threeContainer.value
  camera.aspect = container.clientWidth / container.clientHeight
  camera.updateProjectionMatrix()
  renderer.setSize(container.clientWidth, container.clientHeight)
}

async function loadMesh() {
  if (!segPath.value) {
    statusMessage.value = 'Please select or upload a segmentation first.'
    return
  }
  try {
    isLoadingMesh.value = true
    statusMessage.value = ''

    initThreeIfNeeded()

    const res = await axios.post('http://localhost:5000/viewer/seg3d', {
      seg_path: segPath.value
    })
    if (res.data.error) throw new Error(res.data.error)

    const vertices = res.data.vertices
    const faces = res.data.faces

    const geometry = new THREE.BufferGeometry()
    const positions = new Float32Array(faces.length * 9)

    let idx = 0
    for (let i = 0; i < faces.length; i++) {
      const [a, b, c] = faces[i]
      const va = vertices[a]
      const vb = vertices[b]
      const vc = vertices[c]

      positions[idx++] = va[2]
      positions[idx++] = va[1]
      positions[idx++] = va[0]

      positions[idx++] = vb[2]
      positions[idx++] = vb[1]
      positions[idx++] = vb[0]

      positions[idx++] = vc[2]
      positions[idx++] = vc[1]
      positions[idx++] = vc[0]
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geometry.computeVertexNormals()

    if (mesh) {
      scene.remove(mesh)
      mesh.geometry.dispose()
      mesh.material.dispose()
    }

    const { cx, cy, cz } = getVolumeCenters()

    const mat = new THREE.MeshStandardMaterial({
      color: 0x22c55e,
      metalness: 0.1,
      roughness: 0.5,
      transparent: true,
      opacity: 0.85,
      clippingPlanes: [clipAxial, clipCoronal, clipSagittal],
      clipIntersection: true
    })

    mesh = new THREE.Mesh(geometry, mat)
    mesh.position.set(-cx, -cy, -cz)
    scene.add(mesh)

    // keep the planes feature
    rebuildSlicePlanes()
    updateMeshClippingPlanes()

    statusMessage.value = '3D mesh loaded.'
  } catch (err) {
    console.error(err)
    statusMessage.value = 'Failed to load 3D segmentation: ' + err.message
  } finally {
    isLoadingMesh.value = false
  }
}

/* ---------------- Lifecycle ---------------- */

onMounted(async () => {
  await fetchItems()
  await nextTick()
  resizeAllRoiCanvases()
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  if (animationId) cancelAnimationFrame(animationId)

  if (axialPlane) disposePlane(axialPlane)
  if (coronalPlane) disposePlane(coronalPlane)
  if (sagittalPlane) disposePlane(sagittalPlane)

  if (mesh) {
    mesh.geometry.dispose()
    mesh.material.dispose()
  }

  if (renderer && renderer.domElement && renderer.domElement.parentNode) {
    renderer.domElement.parentNode.removeChild(renderer.domElement)
  }
})
</script>

<style scoped>
.viewer-page {
  padding: 24px;
  background: #0b1120;
  min-height: 100vh;
  box-sizing: border-box;
  color: #e5e7eb;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.header-card {
  background: #020617;
  border-radius: 18px;
  padding: 18px 20px 16px;
  box-shadow:
    0 18px 45px rgba(15, 23, 42, 0.35),
    0 0 0 1px rgba(148, 163, 184, 0.35);
  margin-bottom: 18px;
}

.title {
  margin: 0 0 4px;
  font-size: 1.2rem;
  font-weight: 600;
}

.subtitle {
  margin: 0 0 8px;
  font-size: 0.85rem;
  color: #9ca3af;
}

.field-group {
  margin-bottom: 10px;
}

.field-label {
  display: block;
  font-size: 0.8rem;
  font-weight: 600;
  color: #cbd5f5;
  margin-bottom: 4px;
}

.row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.select-input {
  flex: 1;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid #1f2937;
  background: #020617;
  color: #e5e7eb;
  font-size: 0.85rem;
}

.small-btn,
.primary-btn,
.secondary-btn,
.roi-btn {
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 0.8rem;
  cursor: pointer;
  border: none;
}

.small-btn {
  background: #111827;
  color: #e5e7eb;
  border: 1px solid #1f2937;
}

.primary-btn {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #ffffff;
  margin-right: 6px;
}

.secondary-btn {
  background: #111827;
  color: #e5e7eb;
  border: 1px solid #1f2937;
}

.primary-btn:disabled,
.secondary-btn:disabled,
.roi-btn:disabled,
.small-btn:disabled {
  opacity: 0.55;
  cursor: default;
}

.status-text {
  margin-top: 6px;
  font-size: 0.8rem;
  color: #f97316;
}

.hidden-input {
  display: none;
}

.grid-2x2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-auto-rows: auto;
  gap: 14px;
}

.pane {
  background: #020617;
  border-radius: 16px;
  padding: 12px 10px 10px;
  box-shadow:
    0 18px 35px rgba(15, 23, 42, 0.4),
    0 0 0 1px rgba(30, 64, 175, 0.4);
}

.pane-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #cbd5f5;
  margin-bottom: 6px;
}

.index-label {
  color: #6b7280;
}

.roi-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.roi-btn {
  background: #111827;
  color: #e5e7eb;
  border: 1px solid #1f2937;
}
.roi-btn.primary {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border: none;
}

.slice-frame {
  position: relative;
  width: 100%;
  height: 260px;
  border-radius: 10px;
  overflow: hidden;
  background: #020617;
}

.slice-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform-origin: center center;
}

.sagittal-img {
  top: 50%;
  left: 50%;
  width: 300%;
  height: 200%;
  transform-origin: center center;
}

.coronal-img {
  top: 50%;
  left: 50%;
  width: 300%;
  height: 200%;
  transform-origin: center center;
}

.slice-img.overlay {
  mix-blend-mode: normal;
}

.slider-row {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.slider-label {
  width: 72px;
  font-size: 0.75rem;
  color: #9ca3af;
}

.slider-row input[type='range'] {
  flex: 1;
}

.three-container {
  width: 100%;
  height: 260px;
  border-radius: 10px;
  overflow: hidden;
  background: #020617;
}

.roi-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: auto;
  cursor: crosshair;
}

.empty-hint {
  margin-top: 24px;
  color: #9ca3af;
  font-size: 0.9rem;
}
</style>
