<template>
  <div class="ae-timeline-root">
    <header class="ae-header">
      <div class="header-left">
        <div class="logo">
          <div class="logo-icon">AE</div>
          <span class="logo-text">AE Animator</span>
        </div>
        <div class="header-divider"></div>
        <button class="btn btn-ghost" @click="exportProject" title="保存工程文件">Save</button>
        <button class="btn btn-ghost" @click="triggerLoadProject" title="加载工程文件">Load</button>
      </div>
      <div class="header-center">
        <span class="project-info">{{ store.project.width }}x{{ store.project.height }} @ {{ store.project.fps }} FPS</span>
      </div>
      <div class="header-right">
        <button class="btn btn-primary" @click="addForeground">+ FG Layer</button>
        <button class="btn btn-secondary" @click="addBackground">+ BG Layer</button>
        <div class="header-divider"></div>
        <button class="btn btn-accent" @click="save" title="保存到节点">Save</button>
        <button class="btn btn-close" @click="close" title="关闭">Close</button>
      </div>
    </header>

    <div class="ae-main">
      <aside class="ae-inspector">
        <div class="inspector-card" v-if="store.currentLayer">
          <div class="card-header">
            <span class="layer-title">{{ displayLayerName(store.currentLayer, store.currentLayerIndex) }}</span>
            <span class="layer-badge" :class="store.currentLayer.type">
              {{ store.currentLayer.type === 'background' ? 'BG' : 'FG' }}
            </span>
          </div>
          <div class="card-subtitle">
            Layer {{ store.currentLayerIndex + 1 }} - {{ store.currentLayer.type === 'background' ? 'Background' : 'Foreground' }}
          </div>
        </div>
        <div class="inspector-card empty" v-else>
          <span>请选择一个图层</span>
        </div>

        <div class="inspector-section" v-if="store.currentLayer">
          <div class="section-title">Transform</div>
          <div class="property-list">
            <div class="property-row">
              <span class="prop-label">Position X</span>
              <input type="number" class="prop-input" :value="currentLayerProps.x.toFixed(0)" @input="updateProp('x', $event)" step="1" />
            </div>
            <div class="property-row">
              <span class="prop-label">Position Y</span>
              <input type="number" class="prop-input" :value="currentLayerProps.y.toFixed(0)" @input="updateProp('y', $event)" step="1" />
            </div>
            <div class="property-row">
              <span class="prop-label">Scale</span>
              <input type="number" class="prop-input" :value="(currentLayerProps.scale * 100).toFixed(0)" @input="updateScaleProp($event)" step="1" />
              <span class="prop-unit">%</span>
            </div>
            <div class="property-row">
              <span class="prop-label">Rotation</span>
              <input type="number" class="prop-input" :value="currentLayerProps.rotation.toFixed(0)" @input="updateProp('rotation', $event)" step="1" />
              <span class="prop-unit">deg</span>
            </div>
            <div class="property-row slider-row">
              <div class="slider-header">
                <span class="prop-label">Opacity</span>
                <span class="prop-value">{{ (currentLayerProps.opacity * 100).toFixed(0) }}%</span>
              </div>
              <input type="range" class="prop-slider" :value="currentLayerProps.opacity" @input="updateProp('opacity', $event)" min="0" max="1" step="0.01" />
            </div>
          </div>
        </div>

        <div class="inspector-section">
          <div class="section-title">Tools</div>
          <div class="tools-grid">
            <button class="tool-btn" :class="{active: store.maskMode.enabled}" @click="toggleMode('mask')">Mask Mode</button>
            <button class="tool-btn" :class="{active: store.maskMode.enabled && store.maskMode.erase}" @click="store.maskMode.erase = !store.maskMode.erase" :disabled="!store.maskMode.enabled">Eraser</button>
            <button class="tool-btn" :class="{active: store.pathMode.enabled}" @click="toggleMode('path')">Path Tool</button>
            <button class="tool-btn" :class="{active: store.extractMode.enabled}" @click="toggleMode('extract')">AI Extract</button>
          </div>

          <div class="tool-settings" v-if="store.maskMode.enabled">
            <div class="slider-header">
              <span class="prop-label">Brush Size</span>
              <span class="prop-value">{{ store.maskMode.brush }}px</span>
            </div>
            <input type="range" class="prop-slider" v-model.number="store.maskMode.brush" min="1" max="100" step="1" />
          </div>

          <div class="tool-settings" v-if="store.extractMode.enabled">
            <div class="slider-header">
              <span class="prop-label">Brush Size</span>
              <span class="prop-value">{{ store.extractMode.brush }}px</span>
            </div>
            <input type="range" class="prop-slider" v-model.number="store.extractMode.brush" min="5" max="150" step="1" />
            <div class="extract-actions">
              <button class="btn btn-small btn-primary" @click="applyExtract">Apply</button>
              <button class="btn btn-small btn-ghost" @click="clearExtractSelection">Clear</button>
            </div>
          </div>
        </div>

        <div class="inspector-section">
          <div class="section-title">Actions</div>
          <div class="action-row">
            <button class="btn btn-small btn-ghost" @click="clearCache">Clear Cache</button>
            <button class="btn btn-small btn-ghost" @click="refreshPreview">Refresh</button>
            <button class="btn btn-small btn-accent" @click="runNode">Run</button>
          </div>
          <div class="fit-row">
            <span class="prop-label">Fit Mode</span>
            <select class="fit-select" v-model="fitMode">
              <option value="fit">Fit</option>
              <option value="fill">Fill</option>
              <option value="stretch">Stretch</option>
            </select>
          </div>
        </div>
      </aside>

      <main class="ae-viewport">
        <div class="viewport-bar">
          <span class="duration-text">Duration: {{ formatTime(projectDuration) }}</span>
          <span class="time-text">{{ formatTime(store.currentTime) }}</span>
        </div>
        <div class="viewport-canvas">
          <CanvasPreview ref="canvasPreviewRef" :fitMode="fitMode" />
        </div>
      </main>
    </div>

    <footer class="ae-timeline">
      <div class="timeline-controls">
        <div class="controls-left">
          <button class="btn btn-small btn-ghost" @click="addKeyframe">+ Keyframe</button>
          <button class="btn btn-small btn-ghost" @click="deleteCurrentKeyframe">Del Key</button>
          <button class="btn btn-small btn-ghost" @click="clearAllKeyframes">Clear All</button>
        </div>
        <div class="controls-center">
          <span class="time-display">{{ formatTime(store.currentTime) }}</span>
          <div class="playback-btns">
            <button class="pb-btn" @click="seekToZero">|<</button>
            <button class="play-btn" :class="{playing: store.isPlaying}" @click="store.togglePlayback">
              {{ store.isPlaying ? 'Pause' : 'Play' }}
            </button>
            <button class="pb-btn" @click="seekToEnd">>|</button>
          </div>
        </div>
        <div class="controls-right">
          <button class="nav-btn" @click="moveUp" :disabled="!store.currentLayer">Up</button>
          <button class="nav-btn" @click="moveDown" :disabled="!store.currentLayer">Down</button>
        </div>
      </div>

      <div class="timeline-body">
        <div class="layers-panel">
          <div class="layers-header">Layers ({{ store.layers.length }})</div>
          <div class="layers-list" @scroll="onLayersScroll">
            <div
              v-for="(layer, i) in store.layers"
              :key="layer.id"
              class="layer-item"
              :class="{active: i === store.currentLayerIndex}"
              @click="store.selectLayer(i)"
            >
              <span class="expand-icon" @click.stop="toggleLayerExpand(i)">
                {{ expandedLayers.has(i) ? 'v' : '>' }}
              </span>
              <span class="layer-type" :class="layer.type">{{ layer.type === 'background' ? 'B' : 'F' }}</span>
              <span class="layer-name">{{ displayLayerName(layer, i) }}</span>
              <span class="layer-btns">
                <span class="vis-icon" @click.stop="toggleVis(layer)" :class="{off: layer.hidden}">eye</span>
                <span class="del-icon" @click.stop="store.removeLayer(i)">x</span>
              </span>
            </div>
          </div>
        </div>

        <div class="tracks-panel" ref="timelineRef">
          <div class="tracks-content" :style="{ width: timelineWidth + 'px' }">
            <div class="ruler" @mousedown="onRulerMouseDown">
              <div
                v-for="i in Math.ceil(projectDuration) + 1"
                :key="i"
                class="ruler-tick"
                :style="{ left: ((i - 1) * pixelsPerSecond) + 'px' }"
              >
                <span class="tick-text">{{ i - 1 }}s</span>
              </div>
              <div class="playhead-top" :style="{ left: (store.currentTime * pixelsPerSecond) + 'px' }"></div>
            </div>

            <div class="tracks-list" @dblclick="onTrackDblClick" @scroll="onTracksScroll">
              <template v-for="(layer, layerIdx) in store.layers" :key="layer.id">
                <div
                  class="track-row"
                  :class="{active: layerIdx === store.currentLayerIndex}"
                  @click="store.selectLayer(layerIdx)"
                >
                  <div class="track-bar" :class="layer.type" :style="{ width: (projectDuration * pixelsPerSecond) + 'px' }">
                    <template v-if="!expandedLayers.has(layerIdx)">
                      <div
                        v-for="kf in getAllLayerKeyframes(layer)"
                        :key="kf.time + kf.prop"
                        class="mini-kf"
                        :style="{ left: (kf.time * pixelsPerSecond) + 'px' }"
                      ></div>
                    </template>
                  </div>
                </div>

                <template v-if="expandedLayers.has(layerIdx)">
                  <div
                    v-for="prop in animatableProps"
                    :key="prop.key"
                    class="prop-track-row"
                    :class="{active: layerIdx === store.currentLayerIndex}"
                    @click="store.selectLayer(layerIdx)"
                  >
                    <div class="prop-track" @dblclick.stop="addKeyframeAt($event, layerIdx, prop.key)">
                      <div
                        v-for="kf in getPropertyKeyframes(layer, prop.key)"
                        :key="kf.time"
                        class="keyframe-dot"
                        :class="{selected: isKeyframeSelected(layerIdx, prop.key, kf.time)}"
                        :style="{ left: (kf.time * pixelsPerSecond) + 'px' }"
                        :title="`${prop.label}: ${formatValue(kf.value, prop.key)} @ ${kf.time.toFixed(2)}s`"
                        @mousedown.stop="onKeyframeDragStart($event, layerIdx, prop.key, kf)"
                        @click.stop="selectKeyframe(layerIdx, prop.key, kf.time)"
                        @contextmenu.prevent="deleteKeyframe(layerIdx, prop.key, kf.time)"
                      ></div>
                    </div>
                  </div>
                </template>
              </template>
            </div>

            <div class="playhead-line" :style="{ left: (store.currentTime * pixelsPerSecond) + 'px' }"></div>
          </div>
        </div>
      </div>
    </footer>

    <input ref="fileInput" type="file" accept="image/*" multiple style="display:none" @change="onFile" />
    <input ref="projectInput" type="file" accept=".json" style="display:none" @change="onLoadProject" />
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useTimelineStore } from '@/stores/timelineStore'
import CanvasPreview from '@/components/timeline/CanvasPreview.vue'

const BASE_PIXELS_PER_SECOND = 80

const props = defineProps<{ node: any }>()
const store = useTimelineStore()
const canvasPreviewRef = ref<InstanceType<typeof CanvasPreview> | null>(null)
const fileInput = ref<HTMLInputElement>()
const projectInput = ref<HTMLInputElement>()
const timelineRef = ref<HTMLDivElement>()
const containerWidth = ref(0)
let pendingType: 'foreground' | 'background' = 'foreground'
let isDraggingRuler = false
let resizeObserver: ResizeObserver | null = null

const getWidget = (name: string) => props.node?.widgets?.find((x: any) => x.name === name)
function toNumber(value: any, fallback: number) {
  const num = typeof value === 'number' ? value : parseFloat(value)
  return Number.isFinite(num) ? num : fallback
}

const fitMode = ref<'fit' | 'fill' | 'stretch'>('fit')

const projectDuration = computed(() => {
  const fps = Math.max(1, store.project.fps || 1)
  return store.project.duration || (store.project.total_frames / fps) || 0
})

const pixelsPerSecond = computed(() => {
  const duration = Math.max(0.001, projectDuration.value || 0)
  const width = containerWidth.value || timelineRef.value?.clientWidth || 0
  const fit = width ? width / duration : BASE_PIXELS_PER_SECOND
  return Math.max(BASE_PIXELS_PER_SECOND, fit)
})

const timelineWidth = computed(() => {
  const extra = 120
  const minWidth = 800
  const calculatedWidth = projectDuration.value * pixelsPerSecond.value + extra
  const containerW = containerWidth.value || timelineRef.value?.clientWidth || 0
  return Math.max(calculatedWidth, containerW, minWidth)
})

watch(() => store.extractMode.enabled, (enabled) => {
  if (!enabled) {
    canvasPreviewRef.value?.clearExtractSelection?.()
  }
})

function syncTimelineWidth() {
  if (!timelineRef.value) {
    setTimeout(syncTimelineWidth, 100)
    return
  }
  const rect = timelineRef.value.getBoundingClientRect()
  const parentWidth = timelineRef.value.parentElement?.clientWidth || rect.width || 0
  const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : parentWidth
  const newWidth = Math.max(parentWidth || viewportWidth, 800)
  if (newWidth > 0) {
    containerWidth.value = newWidth
  }
}

onMounted(() => {
  loadFromNodeWidgets()
  syncTimelineWidth()
  if (typeof ResizeObserver !== 'undefined' && timelineRef.value) {
    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry?.contentRect) {
        containerWidth.value = entry.contentRect.width
      }
    })
    resizeObserver.observe(timelineRef.value)
  } else {
    window.addEventListener('resize', syncTimelineWidth)
  }
})

let isDraggingKeyframe = false
let draggingKeyframeData: { layerIdx: number, prop: string, originalTime: number } | null = null

const expandedLayers = ref<Set<number>>(new Set([0]))
const selectedKeyframe = ref<{ layerIdx: number, prop: string, time: number } | null>(null)

const animatableProps = [
  { key: 'x', label: 'X' },
  { key: 'y', label: 'Y' },
  { key: 'scale', label: 'Scl' },
  { key: 'rotation', label: 'Rot' },
  { key: 'opacity', label: 'Op' }
]

const currentLayerProps = computed(() => {
  const layer = store.currentLayer
  if (!layer) return { x: 0, y: 0, scale: 1, rotation: 0, opacity: 1 }
  
  const time = store.currentTime
  const kf = layer.keyframes || {}
  
  return {
    x: interpolateValue(kf.x, time, layer.x || 0),
    y: interpolateValue(kf.y, time, layer.y || 0),
    scale: interpolateValue(kf.scale, time, layer.scale || 1),
    rotation: interpolateValue(kf.rotation, time, layer.rotation || 0),
    opacity: interpolateValue(kf.opacity, time, layer.opacity ?? 1)
  }
})

function interpolateValue(keyframes: any[], time: number, defaultValue: number): number {
  if (!keyframes || keyframes.length === 0) return defaultValue
  const sorted = [...keyframes].sort((a, b) => a.time - b.time)
  if (time <= sorted[0].time) return sorted[0].value
  if (time >= sorted[sorted.length - 1].time) return sorted[sorted.length - 1].value
  for (let i = 0; i < sorted.length - 1; i++) {
    if (time >= sorted[i].time && time <= sorted[i + 1].time) {
      const t = (time - sorted[i].time) / (sorted[i + 1].time - sorted[i].time)
      return sorted[i].value + (sorted[i + 1].value - sorted[i].value) * t
    }
  }
  return defaultValue
}

function updateProp(prop: string, event: Event) {
  const layer = store.currentLayer
  if (!layer) return
  const value = parseFloat((event.target as HTMLInputElement).value)
  if (isNaN(value)) return
  const time = store.currentTime
  if (layer.keyframes && layer.keyframes[prop] && layer.keyframes[prop].length > 0) {
    const kfIndex = layer.keyframes[prop].findIndex((k: any) => Math.abs(k.time - time) < 0.05)
    if (kfIndex >= 0) {
      layer.keyframes[prop][kfIndex] = { time: layer.keyframes[prop][kfIndex].time, value }
    } else {
      layer.keyframes[prop].push({ time, value })
      layer.keyframes[prop].sort((a: any, b: any) => a.time - b.time)
    }
  }
  store.updateLayer(store.currentLayerIndex, { [prop]: value })
}

function updateScaleProp(event: Event) {
  const layer = store.currentLayer
  if (!layer) return
  const percentValue = parseFloat((event.target as HTMLInputElement).value)
  if (isNaN(percentValue)) return
  const value = percentValue / 100
  const time = store.currentTime
  if (layer.keyframes && layer.keyframes.scale && layer.keyframes.scale.length > 0) {
    const kfIndex = layer.keyframes.scale.findIndex((k: any) => Math.abs(k.time - time) < 0.05)
    if (kfIndex >= 0) {
      layer.keyframes.scale[kfIndex] = { time: layer.keyframes.scale[kfIndex].time, value }
    } else {
      layer.keyframes.scale.push({ time, value })
      layer.keyframes.scale.sort((a: any, b: any) => a.time - b.time)
    }
  }
  store.updateLayer(store.currentLayerIndex, { scale: value })
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  const frames = Math.floor((seconds % 1) * store.project.fps)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`
}

function getPropertyKeyframes(layer: any, prop: string) {
  if (!layer.keyframes || !layer.keyframes[prop]) return []
  return layer.keyframes[prop].map((kf: any) => ({ time: kf.time, value: kf.value }))
}

function getAllLayerKeyframes(layer: any) {
  const result: { time: number, prop: string }[] = []
  if (!layer.keyframes) return result
  for (const prop of animatableProps) {
    const kfs = layer.keyframes[prop.key]
    if (kfs) {
      kfs.forEach((kf: any) => result.push({ time: kf.time, prop: prop.key }))
    }
  }
  return result
}

function formatValue(value: number, prop: string): string {
  if (prop === 'opacity') return (value * 100).toFixed(0) + '%'
  if (prop === 'scale') return (value * 100).toFixed(0) + '%'
  return value.toFixed(1)
}

function toggleLayerExpand(layerIdx: number) {
  if (expandedLayers.value.has(layerIdx)) {
    expandedLayers.value.delete(layerIdx)
  } else {
    expandedLayers.value.add(layerIdx)
  }
}

function toggleVis(layer: any) {
  layer.hidden = !layer.hidden
  canvasPreviewRef.value?.scheduleRender?.()
}

function getTimeFromEvent(e: MouseEvent): number {
  if (!timelineRef.value) return 0
  const content = timelineRef.value.querySelector('.tracks-content')
  if (!content) return 0
  
  const rect = content.getBoundingClientRect()
  const scrollLeft = timelineRef.value.scrollLeft
  const clickX = e.clientX - rect.left + scrollLeft

  const pps = pixelsPerSecond.value || BASE_PIXELS_PER_SECOND
  
  if (clickX <= 10) {
    return 0
  }
  
  const time = clickX / pps
  return Math.max(0, Math.min(time, projectDuration.value))
}

function onRulerMouseDown(e: MouseEvent) {
  e.preventDefault()
  isDraggingRuler = true
  store.setCurrentTime(getTimeFromEvent(e))
  
  const onGlobalMove = (moveE: MouseEvent) => {
    if (!isDraggingRuler) return
    store.setCurrentTime(getTimeFromEvent(moveE))
  }
  
  const onGlobalUp = () => {
    isDraggingRuler = false
    document.removeEventListener('mousemove', onGlobalMove)
    document.removeEventListener('mouseup', onGlobalUp)
  }
  
  document.addEventListener('mousemove', onGlobalMove)
  document.addEventListener('mouseup', onGlobalUp)
}

function onTrackDblClick(e: MouseEvent) {
  if (!store.currentLayer) return
  const time = getTimeFromEvent(e)
  store.setCurrentTime(time)
  store.addKeyframe()
}

function addKeyframeAt(e: MouseEvent, layerIdx: number, prop: string) {
  const target = e.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const localX = e.clientX - rect.left
  const pps = pixelsPerSecond.value || BASE_PIXELS_PER_SECOND
  const time = Math.max(0, localX / pps)
  
  const layer = store.layers[layerIdx]
  if (!layer) return
  
  const value = layer[prop] ?? (prop === 'scale' || prop === 'opacity' ? 1 : 0)
  if (!layer.keyframes) layer.keyframes = {}
  if (!layer.keyframes[prop]) layer.keyframes[prop] = []
  
  const existing = layer.keyframes[prop].find((kf: any) => Math.abs(kf.time - time) < 0.05)
  if (!existing) {
    layer.keyframes[prop].push({ time, value })
    layer.keyframes[prop].sort((a: any, b: any) => a.time - b.time)
  }
}

function selectKeyframe(layerIdx: number, prop: string, time: number) {
  selectedKeyframe.value = { layerIdx, prop, time }
  store.selectLayer(layerIdx)
  store.setCurrentTime(time)
}

function isKeyframeSelected(layerIdx: number, prop: string, time: number): boolean {
  const sel = selectedKeyframe.value
  if (!sel) return false
  return sel.layerIdx === layerIdx && sel.prop === prop && Math.abs(sel.time - time) < 0.01
}

function onKeyframeDragStart(e: MouseEvent, layerIdx: number, prop: string, kf: any) {
  e.preventDefault()
  isDraggingKeyframe = true
  draggingKeyframeData = { layerIdx, prop, originalTime: kf.time }
  selectKeyframe(layerIdx, prop, kf.time)
  
  const startX = e.clientX
  const startTime = kf.time
  const pps = pixelsPerSecond.value || BASE_PIXELS_PER_SECOND
  
  const onMove = (moveE: MouseEvent) => {
    if (!isDraggingKeyframe || !draggingKeyframeData) return
    
    const diffX = moveE.clientX - startX
    const diffTime = diffX / pps
    let newTime = Math.max(0, startTime + diffTime)
    
    const layer = store.layers[draggingKeyframeData.layerIdx]
    if (layer?.keyframes?.[draggingKeyframeData.prop]) {
      const kfArr = layer.keyframes[draggingKeyframeData.prop]
      const kfIdx = kfArr.findIndex((k: any) => Math.abs(k.time - draggingKeyframeData!.originalTime) < 0.01)
      if (kfIdx >= 0) {
        kfArr[kfIdx].time = newTime
        draggingKeyframeData.originalTime = newTime
        selectedKeyframe.value!.time = newTime
        store.setCurrentTime(newTime)
      }
    }
  }
  
  const onUp = () => {
    isDraggingKeyframe = false
    draggingKeyframeData = null
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    const layer = store.layers[layerIdx]
    if (layer?.keyframes?.[prop]) {
      layer.keyframes[prop].sort((a: any, b: any) => a.time - b.time)
    }
  }
  
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

function deleteKeyframe(layerIdx: number, prop: string, time: number) {
  const layer = store.layers[layerIdx]
  if (!layer?.keyframes?.[prop]) return
  layer.keyframes[prop] = layer.keyframes[prop].filter((kf: any) => Math.abs(kf.time - time) > 0.01)
  if (selectedKeyframe.value?.layerIdx === layerIdx && 
      selectedKeyframe.value?.prop === prop && 
      Math.abs(selectedKeyframe.value?.time - time) < 0.01) {
    selectedKeyframe.value = null
  }
}

function onLayersScroll(e: Event) {
  if (timelineRef.value) {
    const target = e.target as HTMLElement
    const tracks = timelineRef.value.querySelector('.tracks-list') as HTMLElement
    if (tracks) tracks.scrollTop = target.scrollTop
  }
}

function onTracksScroll(e: Event) {
  const target = e.target as HTMLElement
  const sidebar = document.querySelector('.layers-list') as HTMLElement
  if (sidebar) sidebar.scrollTop = target.scrollTop
}

function loadFromNodeWidgets() {
  if (!props.node?.widgets) return

  const width = toNumber(getWidget('width')?.value, store.project.width)
  const height = toNumber(getWidget('height')?.value, store.project.height)
  const fps = Math.max(1, toNumber(getWidget('fps')?.value, store.project.fps))
  const totalFrames = Math.max(1, Math.round(toNumber(getWidget('total_frames')?.value, store.project.total_frames)))
  const maskExpansion = toNumber(getWidget('mask_expansion')?.value, store.project.mask_expansion)
  const maskFeather = toNumber(getWidget('mask_feather')?.value, store.project.mask_feather)

  let layers: any[] = []
  const rawLayers = getWidget('layers_keyframes')?.value
  if (typeof rawLayers === 'string' && rawLayers.trim()) {
    try {
      const parsed = JSON.parse(rawLayers)
      if (Array.isArray(parsed)) layers = parsed
    } catch (err) {
      console.warn('[AE Timeline] Failed to parse layers_keyframes widget', err)
    }
  } else if (Array.isArray(rawLayers)) {
    layers = rawLayers
  }

  const projectData = {
    width,
    height,
    fps,
    total_frames: totalFrames,
    duration: totalFrames / fps,
    mask_expansion: maskExpansion,
    mask_feather: maskFeather
  }

  store.loadAnimation({
    project: projectData,
    layers
  })

  if (store.layers.length > 0 && store.currentLayerIndex < 0) {
    store.selectLayer(0)
  }
}

function displayLayerName(layer: any, index: number) {
  if (layer.name) return layer.name
  if (layer.type === 'background') return 'Background'
  return `Layer ${index + 1}`
}

function exportProject() {
  const data = store.exportAnimation()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `ae_project_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function triggerLoadProject() {
  projectInput.value?.click()
}

function onLoadProject(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  
  const reader = new FileReader()
  reader.onload = (ev) => {
    try {
      const json = JSON.parse(ev.target?.result as string)
      store.loadAnimation(json)
      console.log('Project loaded successfully')
    } catch (err) {
      console.error('Failed to parse project file', err)
      alert('Project file is corrupted or has invalid format')
    }
  }
  reader.readAsText(file)
  if (projectInput.value) projectInput.value.value = ''
}

function updateWidget(name: string, value: any) {
  const findWidget = (n: string) => props.node?.widgets?.find((x: any) => x.name === n)
  const w = findWidget(name)
  if (!w) return
  w.value = value
  if (w.inputEl) {
    w.inputEl.value = value
    w.inputEl.dispatchEvent(new Event("input"))
  }
  if (w.callback) w.callback(value)
}

function save() {
  if (!props.node?.widgets) {
    console.error('[AE Timeline] Node or widgets not found!')
    return
  }
  
  console.log('[AE Timeline] Saving...')
  
  store.layers.forEach(layer => {
    if (layer.maskCanvas) {
      layer.customMask = layer.maskCanvas.toDataURL()
      console.log(`[AE Timeline] Layer ${layer.id}: Saved mask (len=${layer.customMask.length})`)
    }
  })

  const anim = store.exportAnimation()
  
  anim.layers.forEach((l: any) => {
    if (l.bezierPath && l.bezierPath.length > 0) {
      console.log(`[AE Timeline] Layer ${l.id}: Exporting Path with ${l.bezierPath.length} points`)
    }
  })

  const findWidget = (n: string) => props.node.widgets.find((x: any) => x.name === n)
  const lw = findWidget('layers_keyframes')
  if (lw) {
    const jsonStr = JSON.stringify(anim.layers)
    lw.value = jsonStr
    console.log(`[AE Timeline] Saved layers_keyframes (len=${jsonStr.length})`)
    if (lw.inputEl) {
      lw.inputEl.value = jsonStr
      lw.inputEl.dispatchEvent(new Event("input"))
    }
    if (lw.callback) lw.callback(jsonStr)
    if (props.node.widgets_values) {
      const widgetIndex = props.node.widgets.indexOf(lw)
      if (widgetIndex >= 0) props.node.widgets_values[widgetIndex] = jsonStr
    }
    props.node.setDirtyCanvas?.(true, false)
  } else {
    console.error('[AE Timeline] Widget layers_keyframes not found!')
  }
  
  updateWidget('width', store.project.width)
  updateWidget('height', store.project.height)
  updateWidget('fps', store.project.fps)
  updateWidget('total_frames', store.project.total_frames)
  
  props.node.setDirtyCanvas?.(true, false)
}

function close() {
  save()
  const dialog = document.querySelector('.ae-timeline-dialog') as HTMLDialogElement
  if (dialog) dialog.close()
}

function addKeyframe() { store.addKeyframe() }
function deleteCurrentKeyframe() { store.deleteKeyframe() }
function seekToZero() { store.setCurrentTime(0) }
function seekToEnd() { store.setCurrentTime(projectDuration.value) }

function clearAllKeyframes() {
  if (!store.currentLayer) return
  if (!confirm('纭畾瑕佹竻闄ゅ綋鍓嶅浘灞傜殑鎵€鏈夊叧閿抚鍚楋紵')) return
  
  const layer = store.currentLayer
  const propKeys: string[] = ['x', 'y', 'scale', 'rotation', 'opacity', 'mask_size']
  propKeys.forEach(prop => {
    if (layer.keyframes?.[prop]) {
      layer.keyframes[prop] = []
    }
  })
}

function clearCache() {
  store.layers.forEach((layer, idx) => {
    if (idx !== store.currentLayerIndex) {
      if (layer._cachedImage) {
        delete layer._cachedImage
      }
      console.log(`[AE Timeline] Cleared cache for layer ${layer.id}`)
    }
  })
}

function refreshPreview() {
  canvasPreviewRef.value?.scheduleRender?.()
  console.log('[AE Timeline] Preview refreshed')
}

function runNode() {
  if (props.node) {
    const graph = props.node.graph
    if (graph && (window as any).app) {
      (window as any).app.queuePrompt?.(0)
    }
  }
}

function toggleMode(mode: 'mask' | 'path' | 'extract') {
  const modes = {
    mask: store.maskMode,
    path: store.pathMode,
    extract: store.extractMode
  }
  
  const target = modes[mode]
  const next = !target.enabled
  
  if (mode === 'extract' && next) {
    const bgLayer = store.layers.find(l => l.type === 'background')
    if (!bgLayer) {
      alert('Add a background layer before using extract')
      return
    }
  }
  
  Object.entries(modes).forEach(([key, m]) => {
    if (key !== mode) {
      m.enabled = false
    }
  })
  
  if (!next || mode !== 'extract') {
    canvasPreviewRef.value?.clearExtractSelection?.()
  }
  
  target.enabled = next
}

function clearExtractSelection() {
  canvasPreviewRef.value?.clearExtractSelection?.()
}

function applyExtract() {
  const preview = canvasPreviewRef.value
  if (!preview || typeof preview.applyExtractSelection !== 'function') return
  const result = preview.applyExtractSelection()
  if (!result) {
    alert('Draw an extract selection first')
    return
  }
  if ('error' in result) {
    alert(result.error)
    return
  }

  const fgImg = new Image()
  fgImg.onload = () => {
    const extractedCount = store.layers.filter(l => l.id?.startsWith('extracted_')).length
    store.addLayer({
      id: `extracted_${Date.now()}`,
      name: `Extract ${extractedCount + 1}`,
      type: 'foreground',
      image_data: result.foregroundDataUrl,
      img: fgImg,
      x: 0, y: 0, scale: 1, rotation: 0, opacity: 1, mask_size: 0, keyframes: {}
    })
  }
  fgImg.src = result.foregroundDataUrl

  const bgLayer = store.layers.find(l => l.type === 'background')
  if (bgLayer && result.backgroundDataUrl) {
    const bgImg = new Image()
    bgImg.onload = () => {
      bgLayer.image_data = result.backgroundDataUrl
      bgLayer.img = bgImg
      store.updateLayer(store.layers.indexOf(bgLayer), { image_data: result.backgroundDataUrl })
    }
    bgImg.src = result.backgroundDataUrl
  }

  store.extractMode.enabled = false
  canvasPreviewRef.value?.clearExtractSelection?.()
}

function addForeground() {
  pendingType = 'foreground'
  fileInput.value?.click()
}

function addBackground() {
  pendingType = 'background'
  fileInput.value?.click()
}

function onFile(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files) return
  Array.from(files).forEach((file, i) => {
    const reader = new FileReader()
    reader.onload = (ev) => {
      const data = ev.target?.result as string
      const img = new Image()
      img.onload = () => {
        store.addLayer({
          id: 'uploaded_' + Date.now() + '_' + i,
          name: file.name.replace(/\.[^/.]+$/, ''),
          type: pendingType,
          image_data: data,
          img,
          x: 0, y: 0, scale: 1, rotation: 0, opacity: 1, mask_size: 0, keyframes: {}, bg_mode: 'fit'
        })
      }
      img.src = data
    }
    reader.readAsDataURL(file)
  })
  if (fileInput.value) fileInput.value.value = ''
}

function moveUp() { moveLayer(-1) }
function moveDown() { moveLayer(1) }

function moveLayer(d: number) {
  const i = store.currentLayerIndex
  if (i < 0) return
  const n = i + d
  if (n >= 0 && n < store.layers.length) {
    const l = store.layers[i]
    store.layers.splice(i, 1)
    store.layers.splice(n, 0, l)
    store.selectLayer(n)
  }
}

onBeforeUnmount(() => {
  if (resizeObserver && timelineRef.value) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  window.removeEventListener('resize', syncTimelineWidth)
  save()
})
</script>

<style scoped>
/* ============================================
   AE Animator - iOS Style Layout
   浣跨敤 scoped 鏍峰紡纭繚闅旂
   ============================================ */

.ae-timeline-root {
  width: 100% !important;
  height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
  background: #000 !important;
  color: #fff !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  font-size: 13px !important;
  overflow: hidden !important;
  user-select: none !important;
  box-sizing: border-box !important;
}

.ae-timeline-root * {
  box-sizing: border-box !important;
}

/* ========== Header ========== */
.ae-header {
  height: 48px !important;
  min-height: 48px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 0 16px !important;
  background: #1c1c1e !important;
  border-bottom: 1px solid #38383a !important;
  flex-shrink: 0 !important;
}

.header-left,
.header-center,
.header-right {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.logo {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.logo-icon {
  width: 28px !important;
  height: 28px !important;
  background: linear-gradient(135deg, #bf5af2, #0a84ff) !important;
  border-radius: 6px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 10px !important;
  font-weight: bold !important;
}

.logo-text {
  font-size: 15px !important;
  font-weight: 600 !important;
}

.header-divider {
  width: 1px !important;
  height: 20px !important;
  background: #48484a !important;
  margin: 0 8px !important;
}

.project-info {
  font-size: 12px !important;
  font-family: "SF Mono", Monaco, monospace !important;
  color: #8e8e93 !important;
}

/* ========== Buttons ========== */
.btn {
  padding: 6px 12px !important;
  border: none !important;
  border-radius: 6px !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
  white-space: nowrap !important;
}

.btn:hover { filter: brightness(1.1) !important; }
.btn:active { transform: scale(0.98) !important; }
.btn:disabled { opacity: 0.4 !important; cursor: not-allowed !important; }

.btn-primary { background: #0a84ff !important; color: #fff !important; }
.btn-secondary { background: #3a3a3c !important; color: #fff !important; }
.btn-ghost { background: transparent !important; color: #8e8e93 !important; }
.btn-ghost:hover { background: #2c2c2e !important; color: #fff !important; }
.btn-accent { background: #30d158 !important; color: #fff !important; }
.btn-close { background: #ff453a !important; color: #fff !important; padding: 6px 10px !important; }
.btn-small { padding: 4px 8px !important; font-size: 11px !important; }

/* ========== Main Area ========== */
.ae-main {
  flex: 1 !important;
  display: flex !important;
  flex-direction: row !important;
  overflow: hidden !important;
  min-height: 0 !important;
}

/* ========== Inspector (Left Panel) ========== */
.ae-inspector {
  width: 260px !important;
  min-width: 260px !important;
  max-width: 260px !important;
  background: #1c1c1e !important;
  border-right: 1px solid #38383a !important;
  display: flex !important;
  flex-direction: column !important;
  overflow-y: auto !important;
  padding: 12px !important;
  gap: 12px !important;
  flex-shrink: 0 !important;
}

.inspector-card {
  background: #2c2c2e !important;
  border-radius: 12px !important;
  padding: 12px !important;
  border: 1px solid rgba(255,255,255,0.05) !important;
}

.inspector-card.empty {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-height: 60px !important;
  color: #636366 !important;
  font-size: 12px !important;
}

.card-header {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  margin-bottom: 4px !important;
}

.layer-title {
  font-size: 14px !important;
  font-weight: 600 !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
  max-width: 160px !important;
}

.layer-badge {
  font-size: 9px !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  font-weight: bold !important;
}

.layer-badge.foreground { background: rgba(10,132,255,0.2) !important; color: #0a84ff !important; }
.layer-badge.background { background: rgba(191,90,242,0.2) !important; color: #bf5af2 !important; }

.card-subtitle {
  font-size: 11px !important;
  color: #636366 !important;
}

.inspector-section {
  display: flex !important;
  flex-direction: column !important;
  gap: 8px !important;
}

.section-title {
  font-size: 10px !important;
  font-weight: 700 !important;
  color: #636366 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.5px !important;
  padding: 0 4px !important;
}

.property-list {
  background: #2c2c2e !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  border: 1px solid rgba(255,255,255,0.05) !important;
}

.property-row {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 8px 12px !important;
  border-bottom: 1px solid rgba(255,255,255,0.05) !important;
}

.property-row:last-child { border-bottom: none !important; }

.prop-label {
  font-size: 12px !important;
  color: #8e8e93 !important;
}

.prop-input {
  width: 70px !important;
  padding: 4px 8px !important;
  background: #000 !important;
  border: 1px solid #38383a !important;
  border-radius: 6px !important;
  color: #0a84ff !important;
  font-size: 12px !important;
  font-family: "SF Mono", Monaco, monospace !important;
  text-align: right !important;
}

.prop-input:focus {
  outline: none !important;
  border-color: #0a84ff !important;
}

.prop-unit {
  font-size: 11px !important;
  color: #636366 !important;
  margin-left: 4px !important;
  min-width: 16px !important;
}

.prop-value {
  font-size: 12px !important;
  color: #8e8e93 !important;
  font-family: "SF Mono", Monaco, monospace !important;
}

.slider-row {
  flex-direction: column !important;
  align-items: stretch !important;
  gap: 8px !important;
  padding: 12px !important;
}

.slider-header {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
}

.prop-slider {
  -webkit-appearance: none !important;
  width: 100% !important;
  height: 4px !important;
  background: #48484a !important;
  border-radius: 2px !important;
  cursor: pointer !important;
}

.prop-slider::-webkit-slider-thumb {
  -webkit-appearance: none !important;
  width: 16px !important;
  height: 16px !important;
  background: #fff !important;
  border-radius: 50% !important;
  box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
  cursor: pointer !important;
}

.tools-grid {
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  gap: 8px !important;
}

.tool-btn {
  padding: 10px !important;
  background: #2c2c2e !important;
  border: 1px solid rgba(255,255,255,0.05) !important;
  border-radius: 10px !important;
  color: #8e8e93 !important;
  font-size: 11px !important;
  font-weight: 500 !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}

.tool-btn:hover { background: #3a3a3c !important; color: #fff !important; }
.tool-btn.active { background: #0a84ff !important; color: #fff !important; border-color: #0a84ff !important; }
.tool-btn:disabled { opacity: 0.4 !important; cursor: not-allowed !important; }

.tool-settings {
  background: #2c2c2e !important;
  border-radius: 10px !important;
  padding: 12px !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 8px !important;
}

.extract-actions {
  display: flex !important;
  gap: 8px !important;
  margin-top: 4px !important;
}

.action-row {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 6px !important;
}

.fit-row {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  margin-top: 8px !important;
}

.fit-select {
  padding: 4px 8px !important;
  background: #2c2c2e !important;
  border: 1px solid #38383a !important;
  border-radius: 6px !important;
  color: #fff !important;
  font-size: 11px !important;
  cursor: pointer !important;
}

/* ========== Viewport (Center) ========== */
.ae-viewport {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  background: #000 !important;
  min-width: 0 !important;
  overflow: hidden !important;
}

.viewport-bar {
  height: 40px !important;
  min-height: 40px !important;
  background: #1c1c1e !important;
  border-bottom: 1px solid #38383a !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 0 16px !important;
  flex-shrink: 0 !important;
}

.duration-text {
  font-size: 12px !important;
  color: #636366 !important;
}

.time-text {
  font-size: 14px !important;
  font-weight: 600 !important;
  font-family: "SF Mono", Monaco, monospace !important;
  color: #0a84ff !important;
}

.viewport-canvas {
  flex: 1 !important;
  position: relative !important;
  overflow: hidden !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  background-color: #1c1c1e !important; /* solid dark surface */
}

/* ========== Timeline (Footer) ========== */
.ae-timeline {
  height: 280px !important;
  min-height: 280px !important;
  max-height: 280px !important;
  background: #1c1c1e !important;
  border-top: 1px solid #38383a !important;
  display: flex !important;
  flex-direction: column !important;
  flex-shrink: 0 !important;
}

.timeline-controls {
  height: 44px !important;
  min-height: 44px !important;
  background: #2c2c2e !important;
  border-bottom: 1px solid #38383a !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 0 12px !important;
  flex-shrink: 0 !important;
}

.controls-left,
.controls-center,
.controls-right {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.controls-left {
  min-width: 220px !important;
}

.time-display {
  font-size: 14px !important;
  font-weight: 600 !important;
  font-family: "SF Mono", Monaco, monospace !important;
  color: #0a84ff !important;
  min-width: 90px !important;
  text-align: center !important;
}

.playback-btns {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.pb-btn {
  background: none !important;
  border: none !important;
  color: #636366 !important;
  font-size: 14px !important;
  cursor: pointer !important;
  padding: 4px !important;
}

.pb-btn:hover { color: #fff !important; }

.play-btn {
  width: 36px !important;
  height: 36px !important;
  border-radius: 50% !important;
  background: #0a84ff !important;
  border: none !important;
  color: #fff !important;
  font-size: 14px !important;
  cursor: pointer !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: 0 4px 12px rgba(10,132,255,0.4) !important;
}

.play-btn:hover { transform: scale(1.05) !important; }
.play-btn.playing { background: #ff453a !important; box-shadow: 0 4px 12px rgba(255,69,58,0.4) !important; }

.nav-btn {
  padding: 4px 8px !important;
  background: #3a3a3c !important;
  border: none !important;
  border-radius: 4px !important;
  color: #8e8e93 !important;
  font-size: 10px !important;
  cursor: pointer !important;
}

.nav-btn:hover:not(:disabled) { background: #48484a !important; color: #fff !important; }
.nav-btn:disabled { opacity: 0.3 !important; cursor: not-allowed !important; }

/* ========== Timeline Body ========== */
.timeline-body {
  flex: 1 !important;
  display: flex !important;
  flex-direction: row !important;
  overflow: hidden !important;
  min-height: 0 !important;
}

.layers-panel {
  width: 220px !important;
  min-width: 220px !important;
  max-width: 220px !important;
  background: #1c1c1e !important;
  border-right: 1px solid #38383a !important;
  display: flex !important;
  flex-direction: column !important;
  flex-shrink: 0 !important;
}

.layers-header {
  height: 32px !important;
  min-height: 32px !important;
  padding: 0 12px !important;
  background: #2c2c2e !important;
  border-bottom: 1px solid #38383a !important;
  display: flex !important;
  align-items: center !important;
  font-size: 10px !important;
  font-weight: 700 !important;
  color: #636366 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.5px !important;
  flex-shrink: 0 !important;
}

.layers-list {
  flex: 1 !important;
  overflow-y: auto !important;
}

.layer-item {
  height: 32px !important;
  display: flex !important;
  align-items: center !important;
  padding: 0 8px !important;
  gap: 8px !important;
  border-bottom: 1px solid rgba(255,255,255,0.05) !important;
  cursor: pointer !important;
}

.layer-item:hover { background: #2c2c2e !important; }
.layer-item.active {
  background: rgba(10,132,255,0.15) !important;
  border-left: 2px solid #0a84ff !important;
}

.expand-icon {
  font-size: 10px !important;
  color: #636366 !important;
  width: 16px !important;
  text-align: center !important;
  cursor: pointer !important;
}

.layer-type {
  width: 18px !important;
  height: 18px !important;
  border-radius: 4px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 9px !important;
  font-weight: bold !important;
}

.layer-type.foreground { background: rgba(10,132,255,0.3) !important; color: #0a84ff !important; }
.layer-type.background { background: rgba(191,90,242,0.3) !important; color: #bf5af2 !important; }

.layer-name {
  flex: 1 !important;
  font-size: 12px !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
}

.layer-btns {
  display: flex !important;
  gap: 4px !important;
  opacity: 0.5 !important;
}

.layer-item:hover .layer-btns { opacity: 1 !important; }

.vis-icon, .del-icon {
  font-size: 11px !important;
  cursor: pointer !important;
}

.vis-icon.off { opacity: 0.3 !important; }
.del-icon:hover { color: #ff453a !important; }

/* ========== Tracks Panel ========== */
.tracks-panel {
  flex: 1 !important;
  background: #18181a !important;
  overflow-x: auto !important;
  overflow-y: hidden !important;
  position: relative !important;
  min-width: 0 !important;
}

.tracks-content {
  height: 100% !important;
  min-height: 100% !important;
  position: relative !important;
  display: flex !important;
  flex-direction: column !important;
}

.ruler {
  height: 32px !important;
  min-height: 32px !important;
  background: #2c2c2e !important;
  border-bottom: 1px solid #38383a !important;
  position: relative !important;
  cursor: pointer !important;
  flex-shrink: 0 !important;
}

.ruler-tick {
  position: absolute !important;
  top: 0 !important;
  bottom: 0 !important;
  border-left: 1px solid #38383a !important;
  padding-left: 4px !important;
  pointer-events: none !important;
}

.tick-text {
  font-size: 10px !important;
  color: #636366 !important;
}

.playhead-top {
  position: absolute !important;
  top: 0 !important;
  width: 0 !important;
  height: 0 !important;
  border-left: 6px solid transparent !important;
  border-right: 6px solid transparent !important;
  border-top: 10px solid #ff453a !important;
  transform: translateX(-6px) !important;
  z-index: 20 !important;
  pointer-events: none !important;
}

.tracks-list {
  flex: 1 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}

.track-row {
  height: 32px !important;
  display: flex !important;
  align-items: center !important;
  border-bottom: 1px solid rgba(255,255,255,0.05) !important;
  position: relative !important;
  cursor: pointer !important;
}

.track-row:hover { background: rgba(255,255,255,0.02) !important; }
.track-row.active { background: rgba(10,132,255,0.08) !important; }

.track-bar {
  height: 16px !important;
  border-radius: 8px !important;
  position: relative !important;
  margin-left: 4px !important;
}

.track-bar.foreground {
  background: rgba(10,132,255,0.4) !important;
  border: 1px solid rgba(10,132,255,0.5) !important;
}

.track-bar.background {
  background: rgba(191,90,242,0.4) !important;
  border: 1px solid rgba(191,90,242,0.5) !important;
}

.mini-kf {
  position: absolute !important;
  top: 50% !important;
  width: 6px !important;
  height: 6px !important;
  background: #ff9f0a !important;
  transform: translate(-3px, -3px) rotate(45deg) !important;
  border: 1px solid rgba(0,0,0,0.3) !important;
}

.prop-track-row {
  height: 24px !important;
  display: flex !important;
  align-items: center !important;
  background: rgba(0,0,0,0.2) !important;
  border-bottom: 1px solid rgba(255,255,255,0.03) !important;
  cursor: pointer !important;
}

.prop-track-row.active { background: rgba(10,132,255,0.05) !important; }

.prop-track {
  flex: 1 !important;
  height: 100% !important;
  position: relative !important;
  cursor: crosshair !important;
}

.keyframe-dot {
  position: absolute !important;
  top: 50% !important;
  width: 8px !important;
  height: 8px !important;
  background: #f0c040 !important;
  transform: translate(-4px, -4px) rotate(45deg) !important;
  border: 1px solid rgba(0,0,0,0.4) !important;
  cursor: grab !important;
  z-index: 5 !important;
}

.keyframe-dot:hover {
  transform: translate(-4px, -4px) rotate(45deg) scale(1.2) !important;
  background: #ffdd60 !important;
}

.keyframe-dot.selected {
  background: #ff9f0a !important;
  border-color: #ff453a !important;
  box-shadow: 0 0 6px #ff9f0a !important;
}

.playhead-line {
  position: absolute !important;
  top: 32px !important;
  bottom: 0 !important;
  width: 1px !important;
  background: #ff453a !important;
  pointer-events: none !important;
  z-index: 10 !important;
}

/* ========== Scrollbar ========== */
.ae-timeline-root ::-webkit-scrollbar {
  width: 6px !important;
  height: 6px !important;
}

.ae-timeline-root ::-webkit-scrollbar-track {
  background: transparent !important;
}

.ae-timeline-root ::-webkit-scrollbar-thumb {
  background: #48484a !important;
  border-radius: 3px !important;
}

.ae-timeline-root ::-webkit-scrollbar-thumb:hover {
  background: #636366 !important;
}
</style>
