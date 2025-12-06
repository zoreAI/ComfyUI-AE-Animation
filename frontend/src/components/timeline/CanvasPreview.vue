<template>
  <div class="canvas-preview" ref="containerRef">
    <div class="canvas-wrapper">
      <!-- WebGPU Canvas (hidden when not using GPU) -->
      <canvas 
        v-show="useGPU"
        ref="gpuCanvasRef"
        :width="store.project.width"
        :height="store.project.height"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
        @wheel.prevent="onWheel"
        @contextmenu.prevent
        tabindex="0"
        @keydown="onKeyDown"
      />
      <!-- Canvas 2D Fallback -->
      <canvas 
        v-show="!useGPU"
        ref="canvasRef"
        :width="store.project.width"
        :height="store.project.height"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
        @wheel.prevent="onWheel"
        @contextmenu.prevent
        tabindex="0"
        @keydown="onKeyDown"
      />
      <div class="canvas-info">
        <span v-if="store.currentLayer">
          <span class="gpu-badge" v-if="useGPU">GPU</span>
          Layer {{ store.currentLayerIndex + 1 }} | X:{{ Math.round(store.currentLayer.x || 0) }} Y:{{ Math.round(store.currentLayer.y || 0) }} S:{{ (store.currentLayer.scale || 1).toFixed(2) }} R:{{ Math.round(store.currentLayer.rotation || 0) }}°
        </span>
        <span v-else>No layer selected</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { useTimelineStore } from '@/stores/timelineStore'
import TGPU from 'typegpu'

const store = useTimelineStore()
const canvasRef = ref<HTMLCanvasElement>()
const gpuCanvasRef = ref<HTMLCanvasElement>()
const containerRef = ref<HTMLDivElement>()

let isDragging = false
let dragStartX = 0
let dragStartY = 0
let dragStartLayerX = 0
let dragStartLayerY = 0
let shiftKey = false
let altKey = false

const useGPU = ref(false)
let gpuDevice: GPUDevice | null = null
let gpuContext: GPUCanvasContext | null = null
let gpuFormat: GPUTextureFormat = 'bgra8unorm'

let renderPending = false
let ctx: CanvasRenderingContext2D | null = null
const imageCache = new Map<string, HTMLImageElement>()
const gpuTextureCache = new Map<string, GPUTexture>()
let gpuSampler: GPUSampler | null = null
let gpuPipeline: GPURenderPipeline | null = null
let gpuUniformBuffer: GPUBuffer | null = null
let gpuBindGroupLayout: GPUBindGroupLayout | null = null

// Panorama remap cache to avoid per-frame heavy trig
const panoCache: {
  key?: string
  mapX?: Float32Array
  mapY?: Float32Array
  srcData?: Uint8ClampedArray
  imgW?: number
  imgH?: number
  canvas?: HTMLCanvasElement
  ctx?: CanvasRenderingContext2D | null
  outW?: number
  outH?: number
} = {}

// Pano orbit drag / pan
let isPanoOrbit = false
let isPanoPan = false
let panoDragStartX = 0
let panoDragStartY = 0
let panoStartYaw = 0
let panoStartPitch = 0
let panoStartOffsetX = 0
let panoStartOffsetY = 0

let isCameraPan = false
let cameraDragStartX = 0
let cameraDragStartY = 0
let cameraStartPosX = 0
let cameraStartPosY = 0
let cameraStartPosZ = 0

onMounted(async () => {
  if (canvasRef.value) {
    ctx = canvasRef.value.getContext('2d', { 
      alpha: false,
      desynchronized: true
    })
  }
  await initWebGPU()
  scheduleRender()
})

onUnmounted(() => {
  imageCache.clear()
  destroyGPU()
})


async function initWebGPU() {
  console.log('[Timeline GPU] GPU rendering disabled, using Canvas 2D for stability')
  useGPU.value = false
  return
}

function createGPUPipeline(): GPURenderPipeline | null {
  if (!gpuDevice || !gpuBindGroupLayout) return null

  const shaderCode = `
    struct Uniforms {
      transform: mat4x4<f32>,
      opacity: f32,
    }
    @group(0) @binding(0) var<uniform> uniforms: Uniforms;
    @group(0) @binding(1) var texSampler: sampler;
    @group(0) @binding(2) var tex: texture_2d<f32>;

    struct VSOut { @builtin(position) pos: vec4f, @location(0) uv: vec2f }

    @vertex fn vs(@builtin(vertex_index) i: u32) -> VSOut {
      var p = array<vec2f, 6>(vec2f(-1,-1), vec2f(1,-1), vec2f(1,1), vec2f(-1,-1), vec2f(1,1), vec2f(-1,1));
      var u = array<vec2f, 6>(vec2f(0,1), vec2f(1,1), vec2f(1,0), vec2f(0,1), vec2f(1,0), vec2f(0,0));
      var o: VSOut;
      o.pos = uniforms.transform * vec4f(p[i], 0, 1);
      o.uv = u[i];
      return o;
    }

    @fragment fn fs(@location(0) uv: vec2f) -> @location(0) vec4f {
      let c = textureSample(tex, texSampler, uv);
      return vec4f(c.rgb, c.a * uniforms.opacity);
    }
  `

  return gpuDevice.createRenderPipeline({
    layout: gpuDevice.createPipelineLayout({ bindGroupLayouts: [gpuBindGroupLayout] }),
    vertex: { module: gpuDevice.createShaderModule({ code: shaderCode }), entryPoint: 'vs' },
    fragment: {
      module: gpuDevice.createShaderModule({ code: shaderCode }),
      entryPoint: 'fs',
      targets: [{
        format: gpuFormat,
        blend: {
          color: { srcFactor: 'src-alpha', dstFactor: 'one-minus-src-alpha', operation: 'add' },
          alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' }
        }
      }]
    },
    primitive: { topology: 'triangle-list' }
  })
}

function destroyGPU() {
  for (const tex of gpuTextureCache.values()) tex.destroy()
  gpuTextureCache.clear()
  gpuUniformBuffer?.destroy()
  gpuDevice = null
  gpuContext = null
}

function scheduleRender() {
  if (renderPending) return
  renderPending = true
  requestAnimationFrame(() => {
    renderPending = false
    render()
  })
}

watch(() => [store.layers, store.currentLayer, store.currentTime], () => {
  scheduleRender()
}, { deep: true })

watch(() => store.extractMode.enabled, () => {
  isExtractDrawing = false
  scheduleRender()
})

function renderGPU() {
  if (!gpuDevice || !gpuContext || !gpuPipeline || !gpuSampler || !gpuUniformBuffer || !gpuBindGroupLayout) {
    renderCanvas2D()
    return
  }

  try {
    const encoder = gpuDevice.createCommandEncoder()
    const textureView = gpuContext.getCurrentTexture().createView()

    const renderableLayers: Array<{layer: any, texture: GPUTexture, props: any}> = []
    
    for (const layer of store.layers) {
      if (!layer.image_data && !layer.img) continue
      
      const texture = gpuTextureCache.get(layer.id)
      if (texture && layer.img) {
        renderableLayers.push({
          layer,
          texture,
          props: getLayerProps(layer)
        })
      } else {
        loadGPUTexture(layer)
      }
    }
    const pass = encoder.beginRenderPass({
      colorAttachments: [{
        view: textureView,
        loadOp: 'clear',
        clearValue: { r: 0, g: 0, b: 0, a: 1 },
        storeOp: 'store'
      }]
    })

    pass.setPipeline(gpuPipeline)

    for (const { layer, texture, props } of renderableLayers) {
      const matrix = createTransformMatrix(props, layer.img.width, layer.img.height)
      
      const uniformData = new Float32Array(20)
      uniformData.set(matrix)
      uniformData[16] = props.opacity
      gpuDevice.queue.writeBuffer(gpuUniformBuffer, 0, uniformData)

      const bindGroup = gpuDevice.createBindGroup({
        layout: gpuBindGroupLayout!,
        entries: [
          { binding: 0, resource: { buffer: gpuUniformBuffer } },
          { binding: 1, resource: gpuSampler },
          { binding: 2, resource: texture.createView() }
        ]
      })

      pass.setBindGroup(0, bindGroup)
      pass.draw(6)
    }

    pass.end()
    gpuDevice.queue.submit([encoder.finish()])
  } catch (e) {
    console.warn('[Timeline GPU] Render error:', e)
    useGPU.value = false
    renderCanvas2D()
  }
}

async function loadGPUTexture(layer: any) {
  if (!gpuDevice || gpuTextureCache.has(layer.id)) return
  
  try {
    const img = layer.img || await loadImage(layer.image_data)
    if (!img || !gpuDevice) return
    
    layer.img = img
    
    const texture = gpuDevice.createTexture({
      size: [img.width, img.height],
      format: 'rgba8unorm',
      usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.RENDER_ATTACHMENT
    })

    const imageBitmap = await createImageBitmap(img)
    gpuDevice.queue.copyExternalImageToTexture(
      { source: imageBitmap },
      { texture },
      [img.width, img.height]
    )

    gpuTextureCache.set(layer.id, texture)
    scheduleRender()
  } catch (e) {
    console.warn('[Timeline GPU] Texture load error:', e)
  }
}

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function createTransformMatrix(props: any, imgW: number, imgH: number): Float32Array {
  const canvasW = store.project.width
  const canvasH = store.project.height
  
  const x = props.x / canvasW * 2
  const y = -props.y / canvasH * 2
  const scaleX = (imgW * props.scale) / canvasW
  const scaleY = (imgH * props.scale) / canvasH
  
  const cos = Math.cos(props.rotation * Math.PI / 180)
  const sin = Math.sin(props.rotation * Math.PI / 180)
  return new Float32Array([
    scaleX * cos, scaleX * sin, 0, 0,
    -scaleY * sin, scaleY * cos, 0, 0,
    0, 0, 1, 0,
    x, y, 0, 1
  ])
}

function getCachedImage(layer: any): HTMLImageElement | null {
  if (layer.img) return layer.img
  if (!layer.image_data) return null
  
  const cacheKey = layer.id
  if (imageCache.has(cacheKey)) {
    const img = imageCache.get(cacheKey)!
    if (img.complete) {
      layer.img = img
      return img
    }
    return null
  }
  
  const img = new Image()
  img.onload = () => {
    layer.img = img
    scheduleRender()
  }
  img.src = layer.image_data
  imageCache.set(cacheKey, img)
  return null
}

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

function interpolateBezierPath(path: any[], time: number, duration: number): { x: number, y: number } | null {
  if (!path || path.length < 2) return null
  
  const t = time / duration
  const totalPoints = path.length
  const segmentCount = totalPoints - 1
  const currentSegment = Math.min(Math.floor(t * segmentCount), segmentCount - 1)
  const segmentT = (t * segmentCount) - currentSegment
  
  const p0 = path[currentSegment]
  const p1 = path[currentSegment + 1]
  
  if (!p0 || !p1) return null
  
  const cp1x = p0.cp2x ?? (p0.x + (p1.x - p0.x) / 3)
  const cp1y = p0.cp2y ?? (p0.y + (p1.y - p0.y) / 3)
  const cp2x = p1.cp1x ?? (p0.x + (p1.x - p0.x) * 2 / 3)
  const cp2y = p1.cp1y ?? (p0.y + (p1.y - p0.y) * 2 / 3)
  
  const mt = 1 - segmentT
  const mt2 = mt * mt
  const mt3 = mt2 * mt
  const t2 = segmentT * segmentT
  const t3 = t2 * segmentT
  
  return {
    x: mt3 * p0.x + 3 * mt2 * segmentT * cp1x + 3 * mt * t2 * cp2x + t3 * p1.x,
    y: mt3 * p0.y + 3 * mt2 * segmentT * cp1y + 3 * mt * t2 * cp2y + t3 * p1.y
  }
}

function getLayerProps(layer: any) {
  const time = store.currentTime
  const kf = layer.keyframes || {}
  
  let x = interpolateValue(kf.x, time, layer.x || 0)
  let y = interpolateValue(kf.y, time, layer.y || 0)
  
  if (layer.usePathAnimation && layer.bezierPath && layer.bezierPath.length >= 2) {
    const pathPos = interpolateBezierPath(layer.bezierPath, time, store.project.duration)
    if (pathPos) {
      x = pathPos.x
      y = pathPos.y
    }
  }
  
  return {
    x,
    y,
    z: interpolateValue(kf.z, time, layer.z || 0),
    scale: interpolateValue(kf.scale, time, layer.scale || 1),
    rotation: interpolateValue(kf.rotation, time, layer.rotation || 0),
    opacity: interpolateValue(kf.opacity, time, layer.opacity ?? 1),
    mask_size: interpolateValue(kf.mask_size, time, layer.mask_size || 0),
    rotationX: interpolateValue(kf.rotationX, time, layer.rotationX || 0),
    rotationY: interpolateValue(kf.rotationY, time, layer.rotationY || 0),
    rotationZ: interpolateValue(kf.rotationZ, time, layer.rotationZ || 0),
    anchorX: interpolateValue(kf.anchorX, time, layer.anchorX || 0),
    anchorY: interpolateValue(kf.anchorY, time, layer.anchorY || 0),
    perspective: interpolateValue(kf.perspective, time, layer.perspective || 1000)
  }
}

function render() {
  if (useGPU.value) {
    renderGPU()
    return
  }
  renderCanvas2D()
}

function createViewMatrix(yaw: number, pitch: number, roll: number, posX: number, posY: number, posZ: number): number[] {
  const deg2rad = Math.PI / 180
  const y = yaw * deg2rad
  const p = pitch * deg2rad
  const r = roll * deg2rad
  
  const cy = Math.cos(y), sy = Math.sin(y)
  const cp = Math.cos(p), sp = Math.sin(p)
  const cr = Math.cos(r), sr = Math.sin(r)
  
  const m00 = cy * cp
  const m01 = cy * sp * sr - sy * cr
  const m02 = cy * sp * cr + sy * sr
  const m10 = sy * cp
  const m11 = sy * sp * sr + cy * cr
  const m12 = sy * sp * cr - cy * sr
  const m20 = -sp
  const m21 = cp * sr
  const m22 = cp * cr
  
  return [
    m00, m10, m20, 0,
    -m01, -m11, -m21, 0,
    m02, m12, m22, 0,
    -(m00 * posX + m10 * posY + m20 * posZ),
    -(-m01 * posX + -m11 * posY + -m21 * posZ),
    -(m02 * posX + m12 * posY + m22 * posZ),
    1
  ]
}

function createProjectionMatrix(fov: number, aspect: number, near: number = 0.1, far: number = 10000): number[] {
  const deg2rad = Math.PI / 180
  const f = 1.0 / Math.tan(fov * deg2rad / 2)
  const range = far - near
  
  return [
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, -(far + near) / range, -1,
    0, 0, -(2 * far * near) / range, 0
  ]
}

function multiplyMatrices(a: number[], b: number[]): number[] {
  const result = new Array(16).fill(0)
  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      for (let k = 0; k < 4; k++) {
        result[i * 4 + j] += a[i * 4 + k] * b[k * 4 + j]
      }
    }
  }
  return result
}

function transformPoint3D(matrix: number[], x: number, y: number, z: number): { x: number, y: number, z: number, w: number } {
  const outX = matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12]
  const outY = matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13]
  const outZ = matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14]
  const outW = matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15]
  return { x: outX, y: outY, z: outZ, w: outW }
}

function projectToScreen(point: { x: number, y: number, z: number, w: number }, canvasW: number, canvasH: number): { x: number, y: number, depth: number, visible: boolean } {
  if (Math.abs(point.w) < 1e-6) {
    return { x: 0, y: 0, depth: 0, visible: false }
  }
  
  const invW = 1 / point.w
  const ndcX = point.x * invW
  const ndcY = point.y * invW
  const depth = point.z * invW
  
  const screenX = (ndcX + 1) * 0.5 * canvasW
  const screenY = (1 - ndcY) * 0.5 * canvasH
  
  const visible = depth > -1 && depth < 1 && 
                  ndcX >= -1 && ndcX <= 1 && 
                  ndcY >= -1 && ndcY <= 1
  
  return { x: screenX, y: screenY, depth, visible }
}

function renderCanvas2D() {
  if (!canvasRef.value || !ctx) return

  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, store.project.width, store.project.height)

  const panoEnabled = !!store.project.pano_enable
  const cameraEnabled = !!store.project.cam_enable
  const baseCamOffsetX = store.interpolateProjectValue?.('cam_offset_x', store.currentTime, store.project.cam_offset_x || 0) ?? (store.project.cam_offset_x || 0)
  const baseCamOffsetY = store.interpolateProjectValue?.('cam_offset_y', store.currentTime, store.project.cam_offset_y || 0) ?? (store.project.cam_offset_y || 0)
  const camPosX = store.interpolateProjectValue?.('cam_pos_x', store.currentTime, store.project.cam_pos_x || 0) ?? (store.project.cam_pos_x || 0)
  const camPosY = store.interpolateProjectValue?.('cam_pos_y', store.currentTime, store.project.cam_pos_y || 0) ?? (store.project.cam_pos_y || 0)
  const camPosZ = store.interpolateProjectValue?.('cam_pos_z', store.currentTime, store.project.cam_pos_z || 0) ?? (store.project.cam_pos_z || 0)

  // 相机缩放做夹取，避免“飞出画布”
  const cameraScale = cameraEnabled ? Math.max(0.2, Math.min(4, 1 / (1 + camPosZ * 0.001))) : 1
  const camOffsetX = cameraEnabled ? baseCamOffsetX + camPosX : baseCamOffsetX
  const camOffsetY = cameraEnabled ? baseCamOffsetY + camPosY : baseCamOffsetY

  const bgLayer = store.layers.find(l => l.type === 'background')
  if (bgLayer) {
    drawBackgroundLayer(ctx, bgLayer, camOffsetX, camOffsetY, cameraScale, cameraEnabled)
  }

  store.layers.filter(l => l.type !== 'background').forEach(layer => {
    drawForegroundLayer(ctx, layer, camOffsetX, camOffsetY, cameraEnabled, cameraScale)
  })

  if (store.pathMode.enabled && store.currentLayer?.bezierPath) {
    drawBezierPath(ctx, store.currentLayer.bezierPath)
  }

  if (store.extractMode.enabled) {
    drawExtractOverlay(ctx)
  }
}

function drawBezierPath(ctx: CanvasRenderingContext2D, path: any[]) {
  if (!path || path.length === 0) return
  
  const centerX = store.project.width / 2
  const centerY = store.project.height / 2
  
  ctx.save()
  ctx.strokeStyle = '#ff6b6b'
  ctx.lineWidth = 2
  ctx.setLineDash([5, 5])
  
  ctx.beginPath()
  ctx.moveTo(centerX + path[0].x, centerY + path[0].y)
  
  for (let i = 1; i < path.length; i++) {
    const p0 = path[i - 1]
    const p1 = path[i]
    
    const cp1x = p0.cp2x ?? (p0.x + (p1.x - p0.x) / 3)
    const cp1y = p0.cp2y ?? (p0.y + (p1.y - p0.y) / 3)
    const cp2x = p1.cp1x ?? (p0.x + (p1.x - p0.x) * 2 / 3)
    const cp2y = p1.cp1y ?? (p0.y + (p1.y - p0.y) * 2 / 3)
    
    ctx.bezierCurveTo(
      centerX + cp1x, centerY + cp1y,
      centerX + cp2x, centerY + cp2y,
      centerX + p1.x, centerY + p1.y
    )
  }
  ctx.stroke()
  ctx.setLineDash([])
  
  path.forEach((pt, i) => {
    ctx.beginPath()
    ctx.arc(centerX + pt.x, centerY + pt.y, 6, 0, Math.PI * 2)
    ctx.fillStyle = i === 0 ? '#4ecdc4' : (i === path.length - 1 ? '#ff6b6b' : '#ffe66d')
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()
  })

  if (path.length >= 2) {
    const lastIndex = path.length - 1
    const p0 = path[lastIndex - 1]
    const p1 = path[lastIndex]

    const cp1x = p0.cp2x ?? (p0.x + (p1.x - p0.x) / 3)
    const cp1y = p0.cp2y ?? (p0.y + (p1.y - p0.y) / 3)
    const cp2x = p1.cp1x ?? (p0.x + (p1.x - p0.x) * 2 / 3)
    const cp2y = p1.cp1y ?? (p0.y + (p1.y - p0.y) * 2 / 3)
    const t = 0.99
    const mt = 1 - t
    const dx =
      3 * mt * mt * (cp1x - p0.x) +
      6 * mt * t * (cp2x - cp1x) +
      3 * t * t * (p1.x - cp2x)
    const dy =
      3 * mt * mt * (cp1y - p0.y) +
      6 * mt * t * (cp2y - cp1y) +
      3 * t * t * (p1.y - cp2y)

    const angle = Math.atan2(dy, dx)
    const endX = centerX + p1.x
    const endY = centerY + p1.y
    const arrowLen = 18

    ctx.beginPath()
    ctx.moveTo(endX, endY)
    ctx.lineTo(
      endX - arrowLen * Math.cos(angle - Math.PI / 6),
      endY - arrowLen * Math.sin(angle - Math.PI / 6)
    )
    ctx.moveTo(endX, endY)
    ctx.lineTo(
      endX - arrowLen * Math.cos(angle + Math.PI / 6),
      endY - arrowLen * Math.sin(angle + Math.PI / 6)
    )
    ctx.strokeStyle = '#ff6b6b'
    ctx.lineWidth = 2
    ctx.stroke()
  }

  ctx.restore()
}

function drawBackgroundLayer3D(
  ctx: CanvasRenderingContext2D, 
  layer: any, 
  viewProjMatrix: number[] | null,
  camera3DEnabled: boolean,
  camOffsetX: number,
  camOffsetY: number,
  canvasW: number,
  canvasH: number
) {
  const panoEnabled = store.project.pano_enable
  if (panoEnabled) {
    drawBackgroundLayer(ctx, layer, camOffsetX, camOffsetY, 1, true)
    return
  }
  
  if (!camera3DEnabled || !viewProjMatrix) {
    drawBackgroundLayer(ctx, layer, camOffsetX, camOffsetY, 1, false)
    return
  }

  const img = getCachedImage(layer)
  if (!img || img.width === 0 || img.height === 0) return

  const props = getLayerProps(layer)
  const imgW = img.width
  const imgH = img.height

  const layerX = props.x
  const layerY = props.y
  const layerZ = props.z || 0

  const worldPoint = transformPoint3D(viewProjMatrix, layerX, layerY, layerZ)
  const screen = projectToScreen(worldPoint, canvasW, canvasH)

  if (!screen.visible) return

  ctx.save()
  ctx.globalAlpha = props.opacity

  const perspectiveScale = Math.max(0.01, 1 / Math.max(0.1, -worldPoint.z / worldPoint.w))
  
  const mode = layer.bg_mode || 'fit'
  let baseScale = 1
  if (imgW > 0 && imgH > 0) {
    if (mode === 'fit') {
      baseScale = Math.min(canvasW / imgW, canvasH / imgH)
    } else if (mode === 'fill') {
      baseScale = Math.max(canvasW / imgW, canvasH / imgH)
    } else if (mode === 'stretch') {
      baseScale = Math.min(canvasW / imgW, canvasH / imgH)
    }
  }
  if (!Number.isFinite(baseScale) || baseScale <= 0) baseScale = 1

  const finalScale = props.scale * baseScale * perspectiveScale

  ctx.translate(screen.x + camOffsetX, screen.y + camOffsetY)
  ctx.rotate((props.rotation * Math.PI) / 180)
  ctx.scale(finalScale, finalScale)

  ctx.drawImage(img, -imgW / 2, -imgH / 2, imgW, imgH)

  if (layer === store.currentLayer) {
    ctx.strokeStyle = '#3a7bc8'
    ctx.lineWidth = 2 / finalScale
    ctx.strokeRect(-imgW / 2 - 2, -imgH / 2 - 2, imgW + 4, imgH + 4)
  }

  ctx.restore()
}

function drawForegroundLayer3D(
  ctx: CanvasRenderingContext2D,
  layer: any,
  viewProjMatrix: number[] | null,
  camera3DEnabled: boolean,
  camOffsetX: number,
  camOffsetY: number,
  canvasW: number,
  canvasH: number
) {
  if (!camera3DEnabled || !viewProjMatrix) {
    drawForegroundLayer(ctx, layer, camOffsetX, camOffsetY, false, 1)
    return
  }

  const img = getCachedImage(layer)
  if (!img || img.width === 0 || img.height === 0) return

  const props = getLayerProps(layer)
  const w = img.width
  const h = img.height

  ensureMaskCanvas(layer, w, h)

  const layerX = props.x
  const layerY = props.y
  const layerZ = props.z || 0

  const worldPoint = transformPoint3D(viewProjMatrix, layerX, layerY, layerZ)
  const screen = projectToScreen(worldPoint, canvasW, canvasH)

  if (!screen.visible) return

  ctx.save()
  ctx.globalAlpha = props.opacity

  const perspectiveScale = Math.max(0.01, 1 / Math.max(0.1, -worldPoint.z / worldPoint.w))

  ctx.translate(screen.x + camOffsetX, screen.y + camOffsetY)
  if (props.rotationX !== 0 || props.rotationY !== 0 || props.rotationZ !== 0) {
    const rx = props.rotationX * Math.PI / 180
    const ry = props.rotationY * Math.PI / 180
    const rz = (props.rotationZ || props.rotation || 0) * Math.PI / 180
    
    const cosX = Math.cos(rx)
    const sinX = Math.sin(rx)
    const cosY = Math.cos(ry)
    const sinY = Math.sin(ry)
    const cosZ = Math.cos(rz)
    const sinZ = Math.sin(rz)
    
    const m00 = cosY * cosZ
    const m01 = cosY * sinZ
    const m10 = sinX * sinY * cosZ - cosX * sinZ
    const m11 = sinX * sinY * sinZ + cosX * cosZ
    const m20 = cosX * sinY * cosZ + sinX * sinZ
    const m21 = cosX * sinY * sinZ - sinX * cosZ
    
    const zScale = perspectiveScale / (1 + (sinY * w / 2 + sinX * h / 2) / (props.perspective || 1000))
    
    ctx.transform(
      m00 * zScale, m10 * zScale,
      m01 * zScale, m11 * zScale,
      0, m20 * zScale * h / 2 + m21 * zScale * w / 2
    )
  } else {
    ctx.rotate((props.rotation * Math.PI) / 180)
  }

  const finalScale = props.scale * perspectiveScale
  ctx.scale(finalScale, finalScale)

  const anchorOffsetX = (props.anchorX || 0) * w
  const anchorOffsetY = (props.anchorY || 0) * h
  ctx.translate(-anchorOffsetX, -anchorOffsetY)

  if (layer.maskCanvas) {
    const offscreen = document.createElement('canvas')
    offscreen.width = w
    offscreen.height = h
    const offCtx = offscreen.getContext('2d')

    if (offCtx) {
      offCtx.clearRect(0, 0, w, h)
      offCtx.globalCompositeOperation = 'source-over'
      offCtx.drawImage(img, 0, 0, w, h)
      offCtx.globalCompositeOperation = 'destination-in'
      offCtx.drawImage(layer.maskCanvas, 0, 0, w, h)
      ctx.drawImage(offscreen, 0, 0, w, h)
    }
  } else {
    ctx.drawImage(img, 0, 0, w, h)
  }

  if (layer === store.currentLayer) {
    ctx.strokeStyle = '#3a7bc8'
    ctx.lineWidth = 2 / finalScale
    ctx.strokeRect(-2, -2, w + 4, h + 4)
  }

  ctx.restore()
}

function ensureMaskCanvas(layer: any, imgW: number, imgH: number) {
  if (layer.maskCanvas || !layer.customMask) return

  const maskImg = new Image()
  maskImg.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = maskImg.width || imgW
    canvas.height = maskImg.height || imgH
    const mCtx = canvas.getContext('2d')
    if (mCtx) {
      mCtx.drawImage(maskImg, 0, 0, canvas.width, canvas.height)
      layer.maskCanvas = canvas
      scheduleRender()
    }
  }
  maskImg.src = layer.customMask
}

function drawBackgroundLayer(ctx: CanvasRenderingContext2D, layer: any, camOffsetX = 0, camOffsetY = 0, cameraScale = 1, cameraActive = false) {
  const img = getCachedImage(layer)
  if (!img || img.width === 0 || img.height === 0) return

  const props = getLayerProps(layer)
  const panoEnabled = store.project.pano_enable

  ctx.save()
  ctx.globalAlpha = props.opacity

  const mode = layer.bg_mode || 'fit'
  const canvasW = store.project.width
  const canvasH = store.project.height
  const imgW = img.width
  const imgH = img.height
  let baseScale = 1
  const isPanoCompatible = panoEnabled && imgW > 0 && imgH > 0 && Math.abs(imgW / imgH - 2.0) < 0.35

  if (isPanoCompatible) {
    const yaw = store.interpolateProjectValue?.('cam_yaw', store.currentTime, store.project.cam_yaw || 0) ?? (store.project.cam_yaw || 0)
    const pitch = store.interpolateProjectValue?.('cam_pitch', store.currentTime, store.project.cam_pitch || 0) ?? (store.project.cam_pitch || 0)
    const roll = store.interpolateProjectValue?.('cam_roll', store.currentTime, store.project.cam_roll || 0) ?? (store.project.cam_roll || 0)
    const fov = Math.min(170, Math.max(10, store.interpolateProjectValue?.('cam_fov', store.currentTime, store.project.cam_fov || 90) ?? (store.project.cam_fov || 90)))
    const deg2rad = Math.PI / 180
    const maxPreview = 1024
    let prevW = canvasW
    let prevH = canvasH
    const scaleDown = Math.max(1, Math.max(canvasW, canvasH) / maxPreview)
    if (scaleDown > 1.01) {
      prevW = Math.max(1, Math.round(canvasW / scaleDown))
      prevH = Math.max(1, Math.round(canvasH / scaleDown))
    }

    const key = `${prevW}x${prevH}|${imgW}x${imgH}|${yaw}|${pitch}|${roll}|${fov}`
    const needRebuild = panoCache.key !== key

    if (needRebuild) {
      const srcCanvas = document.createElement('canvas')
      srcCanvas.width = imgW
      srcCanvas.height = imgH
      const sctx = srcCanvas.getContext('2d')
      if (sctx) {
        sctx.drawImage(img, 0, 0, imgW, imgH)
        panoCache.srcData = sctx.getImageData(0, 0, imgW, imgH).data
      } else {
        panoCache.srcData = undefined
      }

      const aspect = canvasW / Math.max(1, canvasH)
      const tanHalfFov = Math.tan((fov * deg2rad) / 2)
      const cy = Math.cos(yaw * deg2rad), sy = Math.sin(yaw * deg2rad)
      const cp = Math.cos(pitch * deg2rad), sp = Math.sin(pitch * deg2rad)
      const cr = Math.cos(roll * deg2rad), sr = Math.sin(roll * deg2rad)
      const R = [
        cr * cy + sr * sp * sy,  sr * cp,  cr * -sy + sr * sp * cy,
        -sr * cy + cr * sp * sy, cr * cp,  -sr * -sy + cr * sp * cy,
        cp * sy,                -sp,       cp * cy
      ]

      const mapX = new Float32Array(prevW * prevH)
      const mapY = new Float32Array(prevW * prevH)
      for (let yPix = 0; yPix < prevH; yPix++) {
        const ny = (yPix + 0.5) / prevH * 2 - 1
        for (let xPix = 0; xPix < prevW; xPix++) {
          const nx = (xPix + 0.5) / prevW * 2 - 1
          let vx = nx * tanHalfFov * aspect
          let vy = -ny * tanHalfFov
          let vz = 1
          const invLen = 1 / Math.hypot(vx, vy, vz)
          vx *= invLen; vy *= invLen; vz *= invLen
          const rx = R[0] * vx + R[1] * vy + R[2] * vz
          const ry = R[3] * vx + R[4] * vy + R[5] * vz
          const rz = R[6] * vx + R[7] * vy + R[8] * vz
          const lon = Math.atan2(rx, rz)
          const lat = Math.asin(Math.max(-1, Math.min(1, ry)))
          const u = ((lon / (Math.PI * 2)) + 0.5) * imgW
          const v = ((-lat / Math.PI) + 0.5) * imgH
          let ui = Math.floor(u) % imgW; if (ui < 0) ui += imgW
          let vi = Math.floor(v); vi = Math.max(0, Math.min(imgH - 1, vi))
          const idx = yPix * prevW + xPix
          mapX[idx] = ui
          mapY[idx] = vi
        }
      }
      panoCache.key = key
      panoCache.mapX = mapX
      panoCache.mapY = mapY
      panoCache.imgW = imgW
      panoCache.imgH = imgH
      panoCache.outW = prevW
      panoCache.outH = prevH

      panoCache.canvas = document.createElement('canvas')
      panoCache.canvas.width = prevW
      panoCache.canvas.height = prevH
      panoCache.ctx = panoCache.canvas.getContext('2d')
    }

    const srcData = panoCache.srcData
    const mapX = panoCache.mapX
    const mapY = panoCache.mapY
    const pCanvas = panoCache.canvas
    const pCtx = panoCache.ctx
    const outW = panoCache.outW || 0
    const outH = panoCache.outH || 0
  if (srcData && mapX && mapY && pCanvas && pCtx && outW > 0 && outH > 0) {
      const dstImage = pCtx.getImageData(0, 0, outW, outH)
      const data = dstImage.data
      const len = outW * outH
      for (let idx = 0; idx < len; idx++) {
        const ui = mapX[idx]
        const vi = mapY[idx]
        const si = (vi * imgW + ui) * 4
        const di = idx * 4
        data[di] = srcData[si]
        data[di + 1] = srcData[si + 1]
        data[di + 2] = srcData[si + 2]
        data[di + 3] = 255
      }
      pCtx.putImageData(dstImage, 0, 0)
      ctx.translate(canvasW / 2 + camOffsetX * cameraScale, canvasH / 2 + camOffsetY * cameraScale)
      ctx.scale(cameraScale, cameraScale)
      ctx.drawImage(pCanvas, -canvasW / 2, -canvasH / 2, canvasW, canvasH)
    } else {
      ctx.restore()
      return drawBackgroundLayer(ctx, { ...layer, panoFallback: true, type: layer.type, bg_mode: layer.bg_mode }, camOffsetX, camOffsetY, cameraScale, cameraActive)
    }
  } else {
    if (imgW > 0 && imgH > 0) {
      if (mode === 'fit') {
        baseScale = Math.min(canvasW / imgW, canvasH / imgH)
      } else if (mode === 'fill') {
        baseScale = Math.max(canvasW / imgW, canvasH / imgH)
      } else if (mode === 'stretch') {
        baseScale = Math.min(canvasW / imgW, canvasH / imgH)
      }
    }

    if (!Number.isFinite(baseScale) || baseScale <= 0) baseScale = 1

    // 获取摄像机参数
    const camYaw = cameraActive ? (store.interpolateProjectValue?.('cam_yaw', store.currentTime, store.project.cam_yaw || 0) ?? (store.project.cam_yaw || 0)) : 0
    const camPitch = cameraActive ? (store.interpolateProjectValue?.('cam_pitch', store.currentTime, store.project.cam_pitch || 0) ?? (store.project.cam_pitch || 0)) : 0
    
    const depthMul = 1 / Math.max(0.1, 1 + (props.z || 0) * 0.001)
    const camMul = cameraActive ? cameraScale : 1
    const camX = cameraActive ? camOffsetX : 0
    const camY = cameraActive ? camOffsetY : 0
    const parallax = cameraActive ? depthMul : 1
    
    // 计算摄像机旋转对背景位置的影响
    let bgX = props.x
    let bgY = props.y
    if (cameraActive && (camYaw !== 0 || camPitch !== 0)) {
      const yawRad = camYaw * Math.PI / 180
      const pitchRad = camPitch * Math.PI / 180
      const bgZ = props.z || 0
      // 背景图层的视差效果更强
      bgX -= Math.tan(yawRad) * (bgZ + 1000) * 0.3
      bgY -= Math.tan(pitchRad) * (bgZ + 1000) * 0.3
    }
    
    ctx.translate(
      canvasW / 2 + (bgX + camX * parallax) * camMul,
      canvasH / 2 + (bgY + camY * parallax) * camMul
    )
    ctx.rotate((props.rotation * Math.PI) / 180)
    ctx.scale(props.scale * baseScale * camMul * depthMul, props.scale * baseScale * camMul * depthMul)

    ctx.drawImage(img, -imgW / 2, -imgH / 2, imgW, imgH)
  }

  if (!cameraActive && layer === store.currentLayer) {
    ctx.strokeStyle = '#3a7bc8'
    ctx.lineWidth = 2 / (props.scale * baseScale)
    ctx.strokeRect(-imgW / 2 - 2, -imgH / 2 - 2, imgW + 4, imgH + 4)
  }

  ctx.restore()
}

function drawForegroundLayer(ctx: CanvasRenderingContext2D, layer: any, camOffsetX = 0, camOffsetY = 0, cameraActive = false, cameraScale = 1) {
  const img = getCachedImage(layer)
  if (!img || img.width === 0 || img.height === 0) return

  const props = getLayerProps(layer)
  const w = img.width
  const h = img.height

  ensureMaskCanvas(layer, w, h)

  ctx.save()
  
  // 获取摄像机参数
  const camYaw = cameraActive ? (store.interpolateProjectValue?.('cam_yaw', store.currentTime, store.project.cam_yaw || 0) ?? (store.project.cam_yaw || 0)) : 0
  const camPitch = cameraActive ? (store.interpolateProjectValue?.('cam_pitch', store.currentTime, store.project.cam_pitch || 0) ?? (store.project.cam_pitch || 0)) : 0
  const camFov = cameraActive ? (store.interpolateProjectValue?.('cam_fov', store.currentTime, store.project.cam_fov || 90) ?? (store.project.cam_fov || 90)) : 90
  
  const depthMul = 1 / Math.max(0.1, 1 + (props.z || 0) * 0.001)
  const camMul = cameraActive ? cameraScale : 1
  const camX = cameraActive ? camOffsetX : 0
  const camY = cameraActive ? camOffsetY : 0
  const parallax = cameraActive ? depthMul : 1
  
  // 计算摄像机旋转对图层位置的影响
  let layerX = props.x
  let layerY = props.y
  if (cameraActive && (camYaw !== 0 || camPitch !== 0)) {
    const yawRad = camYaw * Math.PI / 180
    const pitchRad = camPitch * Math.PI / 180
    const layerZ = props.z || 0
    // 简化的 3D 投影：摄像机旋转会导致图层位置偏移
    layerX -= Math.tan(yawRad) * (layerZ + 500) * 0.5
    layerY -= Math.tan(pitchRad) * (layerZ + 500) * 0.5
  }
  
  ctx.translate(
    store.project.width / 2 + (layerX + camX * parallax) * camMul,
    store.project.height / 2 + (layerY + camY * parallax) * camMul
  )
  
  // 图层自身的 3D 旋转
  if (props.rotationX !== 0 || props.rotationY !== 0) {
    const perspective = props.perspective || 1000
    const rx = props.rotationX * Math.PI / 180
    const ry = props.rotationY * Math.PI / 180
    
    const cosX = Math.cos(rx)
    const sinX = Math.sin(rx)
    const cosY = Math.cos(ry)
    const sinY = Math.sin(ry)
    
    const zScale = 1 / (1 + (sinY * w / 2 + sinX * h / 2) / perspective)
    
    ctx.transform(
      cosY * zScale, sinX * sinY * zScale,
      0, cosX * zScale,
      0, 0
    )
  }
  
  ctx.rotate((props.rotation * Math.PI) / 180)
  const scaleApplied = props.scale * camMul * depthMul
  ctx.scale(scaleApplied, scaleApplied)
  ctx.globalAlpha = props.opacity

  const anchorOffsetX = (props.anchorX || 0) * w
  const anchorOffsetY = (props.anchorY || 0) * h

  if (layer.maskCanvas) {
    const offscreen = document.createElement('canvas')
    offscreen.width = w
    offscreen.height = h
    const offCtx = offscreen.getContext('2d')

    if (offCtx) {
      offCtx.clearRect(0, 0, w, h)
      offCtx.drawImage(img, 0, 0, w, h)
      offCtx.globalCompositeOperation = 'destination-in'
      offCtx.drawImage(layer.maskCanvas, 0, 0, w, h)
      ctx.drawImage(
        offscreen,
        -w / 2 - anchorOffsetX,
        -h / 2 - anchorOffsetY,
        w,
        h
      )
    } else {
      ctx.drawImage(img, -w / 2 - anchorOffsetX, -h / 2 - anchorOffsetY, w, h)
    }
  } else {
    ctx.drawImage(img, -w / 2 - anchorOffsetX, -h / 2 - anchorOffsetY, w, h)
  }

  if (layer === store.currentLayer && layer.img) {
    ctx.strokeStyle = '#3a7bc8'
    ctx.lineWidth = 2 / props.scale
    const w = layer.img.width
    const h = layer.img.height
    ctx.strokeRect(-w / 2 - 2, -h / 2 - 2, w + 4, h + 4)
    
    ctx.fillStyle = '#3a7bc8'
    const corners = [[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]]
    corners.forEach(([cx, cy]) => {
      ctx.fillRect(cx - 4/props.scale, cy - 4/props.scale, 8/props.scale, 8/props.scale)
    })
  }

  if (props.mask_size > 0) {
    ctx.strokeStyle = '#3ac88e'
    ctx.lineWidth = 2 / props.scale
    ctx.setLineDash([5 / props.scale, 5 / props.scale])
    const w = layer.img ? layer.img.width : 512
    const h = layer.img ? layer.img.height : 512
    const maskW = w * props.mask_size
    const maskH = h * props.mask_size
    ctx.strokeRect(-maskW / 2, -maskH / 2, maskW, maskH)
    ctx.setLineDash([])
  }

  ctx.restore()
}

function getActiveCanvas(): HTMLCanvasElement | null {
  return useGPU.value ? gpuCanvasRef.value || null : canvasRef.value || null
}

function getCanvasCoords(e: MouseEvent) {
  const canvas = getActiveCanvas()
  if (!canvas) return { x: 0, y: 0 }
  
  const rect = canvas.getBoundingClientRect()
  const scaleX = store.project.width / rect.width
  const scaleY = store.project.height / rect.height
  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY
  }
}

let isMaskDrawing = false
let maskCtx: CanvasRenderingContext2D | null = null

let extractMaskCanvas: HTMLCanvasElement | null = null
let extractMaskCtx: CanvasRenderingContext2D | null = null
let isExtractDrawing = false
let extractSourceLayerId: string | null = null

let isPathEditing = false
let selectedPathPoint = -1

function onMouseDown(e: MouseEvent) {
  getActiveCanvas()?.focus()
  shiftKey = e.shiftKey
  altKey = e.altKey
  
  const coords = getCanvasCoords(e)

  const panoReady = store.project.pano_enable && !store.maskMode.enabled && !store.extractMode.enabled && !store.pathMode.enabled
  if (panoReady) {
    panoDragStartX = coords.x
    panoDragStartY = coords.y
    panoStartYaw = store.project.cam_yaw || 0
    panoStartPitch = store.project.cam_pitch || 0
    panoStartOffsetX = store.project.cam_offset_x || 0
    panoStartOffsetY = store.project.cam_offset_y || 0
    if (e.button === 1 || e.button === 2) {
      isPanoOrbit = true
      return
    } else if (e.button === 0 && (!store.currentLayer || e.altKey)) {
      isPanoPan = true
      return
    }
  }

  const camera3DEnabled = !!(store.project.cam_enable)
  const cameraReady = camera3DEnabled && !store.project.pano_enable && !store.maskMode.enabled && !store.extractMode.enabled && !store.pathMode.enabled
  
  if (cameraReady) {
    cameraDragStartX = coords.x
    cameraDragStartY = coords.y
    cameraStartPosX = store.project.cam_pos_x || 0
    cameraStartPosY = store.project.cam_pos_y || 0
    cameraStartPosZ = store.project.cam_pos_z || 0
    panoStartYaw = store.project.cam_yaw || 0
    panoStartPitch = store.project.cam_pitch || 0
    
    if (e.button === 1 || e.button === 2) {
      isPanoOrbit = true
      return
    }
    
    if (e.button === 0 && !store.currentLayer) {
      isCameraPan = true
      return
    }
  }
  
  if (!store.currentLayer) return
  
  if (store.extractMode.enabled) {
    const resources = ensureExtractResources()
    if (!resources) {
      console.warn('[Timeline] Extract mode requires a background layer with image data')
      return
    }
    isExtractDrawing = true
    drawExtractPoint(coords.x, coords.y, e.button === 2 || e.altKey)
    return
  }
  
  if (store.maskMode.enabled) {
    isMaskDrawing = true
    initMaskCanvas()
    drawMaskPoint(coords.x, coords.y)
    return
  }
  
  if (store.pathMode.enabled) {
    handlePathClick(coords, e)
    return
  }
  
  isDragging = true
  dragStartX = coords.x
  dragStartY = coords.y
  
  const props = getLayerProps(store.currentLayer)
  dragStartLayerX = props.x
  dragStartLayerY = props.y
}

function onMouseMove(e: MouseEvent) {
  const coords = getCanvasCoords(e)

  if (isPanoOrbit) {
    const dx = coords.x - panoDragStartX
    const dy = coords.y - panoDragStartY
    const yaw = panoStartYaw + dx * 0.2
    const pitch = Math.max(-89, Math.min(89, panoStartPitch + dy * 0.2))
    store.setProject({ cam_yaw: yaw, cam_pitch: pitch })
    store.setProjectKeyframe?.('cam_yaw', store.currentTime, yaw)
    store.setProjectKeyframe?.('cam_pitch', store.currentTime, pitch)
    scheduleRender()
    return
  }

  if (isCameraPan) {
    const dx = coords.x - cameraDragStartX
    const dy = coords.y - cameraDragStartY
    const nextX = cameraStartPosX + dx
    const nextY = cameraStartPosY + dy
    store.setProject({ cam_pos_x: nextX, cam_pos_y: nextY })
    store.setProjectKeyframe?.('cam_pos_x', store.currentTime, nextX)
    store.setProjectKeyframe?.('cam_pos_y', store.currentTime, nextY)
    scheduleRender()
    return
  }

  if (isPanoPan) {
    const dx = coords.x - panoDragStartX
    const dy = coords.y - panoDragStartY
    const nextX = (panoStartOffsetX || 0) + dx
    const nextY = (panoStartOffsetY || 0) + dy
    store.setProject({ cam_offset_x: nextX, cam_offset_y: nextY })
    store.setProjectKeyframe?.('cam_offset_x', store.currentTime, nextX)
    store.setProjectKeyframe?.('cam_offset_y', store.currentTime, nextY)
    scheduleRender()
    return
  }

  if (store.extractMode.enabled && isExtractDrawing) {
    drawExtractPoint(coords.x, coords.y, (e.buttons & 2) === 2 || e.altKey)
    return
  }
  
  if (isMaskDrawing && store.maskMode.enabled) {
    drawMaskPoint(coords.x, coords.y)
    return
  }
  
  if (isPathEditing && selectedPathPoint >= 0) {
    updatePathPoint(coords)
    return
  }
  
  if (!isDragging || !store.currentLayer) return
  
  let dx = coords.x - dragStartX
  let dy = coords.y - dragStartY
  
  if (e.shiftKey) {
    if (Math.abs(dx) > Math.abs(dy)) dy = 0
    else dx = 0
  }
  
  const newX = dragStartLayerX + dx
  const newY = dragStartLayerY + dy
  
  updateLayerWithKeyframes(store.currentLayer, 'x', newX)
  updateLayerWithKeyframes(store.currentLayer, 'y', newY)
  
  scheduleRender()
}

function updateLayerWithKeyframes(layer: any, prop: string, value: number) {
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

function initMaskCanvas() {
  const layer = store.currentLayer
  if (!layer || !layer.img) return
  
  if (!layer.maskCanvas) {
    layer.maskCanvas = document.createElement('canvas')
    layer.maskCanvas.width = layer.img.width
    layer.maskCanvas.height = layer.img.height
    maskCtx = layer.maskCanvas.getContext('2d')
    
    if (maskCtx) {
      if (layer.customMask) {
        const img = new Image()
        img.onload = () => {
          maskCtx?.drawImage(img, 0, 0)
          scheduleRender()
        }
        img.src = layer.customMask
      } else {
        maskCtx.globalCompositeOperation = 'source-over'
        maskCtx.fillStyle = 'white'
        maskCtx.fillRect(0, 0, layer.maskCanvas.width, layer.maskCanvas.height)
      }
    }
  } else {
    maskCtx = layer.maskCanvas.getContext('2d')
  }
}

function drawMaskPoint(canvasX: number, canvasY: number) {
  const layer = store.currentLayer
  if (!layer) return

  if (!maskCtx || !layer.maskCanvas) {
    initMaskCanvas()
  }

  if (!layer.img || !maskCtx || !layer.maskCanvas) return
  
  const props = getLayerProps(layer)
  const centerX = store.project.width / 2 + props.x
  const centerY = store.project.height / 2 + props.y
  
  const localX = (canvasX - centerX) / props.scale + layer.img.width / 2
  const localY = (canvasY - centerY) / props.scale + layer.img.height / 2
  
  const brush = store.maskMode.brush || 20
  
  maskCtx.save()
  maskCtx.beginPath()
  maskCtx.arc(localX, localY, brush, 0, Math.PI * 2)
  
  if (!store.maskMode.erase) {
    maskCtx.globalCompositeOperation = 'destination-out'
    maskCtx.fillStyle = 'black'
  } else {
    maskCtx.globalCompositeOperation = 'source-over'
    maskCtx.fillStyle = 'white'
  }
  
  maskCtx.fill()
  maskCtx.restore()
  
  scheduleRender()
}

function ensureExtractResources() {
  const bgLayer = store.layers.find(l => l.type === 'background')
  if (!bgLayer) return null
  const img = getCachedImage(bgLayer)
  if (!img) return null

  if (
    !extractMaskCanvas ||
    !extractMaskCtx ||
    extractMaskCanvas.width !== img.width ||
    extractMaskCanvas.height !== img.height ||
    extractSourceLayerId !== bgLayer.id
  ) {
    extractMaskCanvas = document.createElement('canvas')
    extractMaskCanvas.width = img.width
    extractMaskCanvas.height = img.height
    extractMaskCtx = extractMaskCanvas.getContext('2d')
    if (extractMaskCtx) {
      extractMaskCtx.clearRect(0, 0, img.width, img.height)
    }
    extractSourceLayerId = bgLayer.id || null
  }

  return {
    layer: bgLayer,
    img,
    ctx: extractMaskCtx!
  }
}

function drawExtractPoint(canvasX: number, canvasY: number, erase = false) {
  const resources = ensureExtractResources()
  if (!resources) return

  const { layer, img, ctx } = resources
  const props = getLayerProps(layer)
  const centerX = store.project.width / 2 + (props.x ?? 0)
  const centerY = store.project.height / 2 + (props.y ?? 0)
  const scale = props.scale ?? 1

  const localX = (canvasX - centerX) / scale + img.width / 2
  const localY = (canvasY - centerY) / scale + img.height / 2

  const brush = Math.max(1, store.extractMode.brush || 30)

  ctx.beginPath()
  ctx.arc(localX, localY, brush, 0, Math.PI * 2)
  ctx.fillStyle = erase ? 'black' : 'white'
  ctx.fill()

  scheduleRender()
}

function drawExtractOverlay(ctx: CanvasRenderingContext2D) {
  if (!store.extractMode.enabled || !extractMaskCanvas || !extractSourceLayerId) return
  const bgLayer = store.layers.find(l => l.id === extractSourceLayerId)
  if (!bgLayer) return
  const img = getCachedImage(bgLayer)
  if (!img) return

  const props = getLayerProps(bgLayer)
  ctx.save()
  ctx.translate(store.project.width / 2 + (props.x ?? 0), store.project.height / 2 + (props.y ?? 0))
  ctx.rotate((props.rotation ?? 0) * Math.PI / 180)
  ctx.scale(props.scale ?? 1, props.scale ?? 1)
  
  const dx = -img.width / 2
  const dy = -img.height / 2
  
  ctx.fillStyle = 'rgba(0, 0, 0, 0.65)'
  ctx.fillRect(dx, dy, img.width, img.height)

  ctx.globalCompositeOperation = 'destination-out'
  ctx.drawImage(extractMaskCanvas, dx, dy, img.width, img.height)

  ctx.restore()
}

function clearExtractSelection() {
  if (extractMaskCtx && extractMaskCanvas) {
    extractMaskCtx.clearRect(0, 0, extractMaskCanvas.width, extractMaskCanvas.height)
    scheduleRender()
  }
}

function hasExtractSelection() {
  if (!extractMaskCtx || !extractMaskCanvas) return false
  const data = extractMaskCtx.getImageData(0, 0, extractMaskCanvas.width, extractMaskCanvas.height).data
  for (let i = 0; i < data.length; i += 4) {
    if (data[i] > 10) return true
  }
  return false
}

function inpaintSimple(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const original = ctx.canvas
  
  const tempC = document.createElement('canvas')
  tempC.width = width
  tempC.height = height
  const tCtx = tempC.getContext('2d')
  if (!tCtx) return null

  tCtx.drawImage(original, 0, 0)
  
  const steps = 20
  tCtx.globalCompositeOperation = 'destination-over'
  
  for (let i = 0; i < steps; i++) {
    tCtx.drawImage(tempC, 1, 0)
    tCtx.drawImage(tempC, -1, 0)
    tCtx.drawImage(tempC, 0, 1)
    tCtx.drawImage(tempC, 0, -1)
    
    if (i % 2 === 0) {
        tCtx.drawImage(tempC, 1, 1)
        tCtx.drawImage(tempC, -1, -1)
        tCtx.drawImage(tempC, 1, -1)
        tCtx.drawImage(tempC, -1, 1)
    }
  }
  for (let i = 0; i < 10; i++) {
    tCtx.drawImage(tempC, 2, 0)
    tCtx.drawImage(tempC, -2, 0)
    tCtx.drawImage(tempC, 0, 2)
    tCtx.drawImage(tempC, 0, -2)
    tCtx.drawImage(tempC, 2, 2)
    tCtx.drawImage(tempC, -2, -2)
    tCtx.drawImage(tempC, 2, -2)
    tCtx.drawImage(tempC, -2, 2)
  }

  return tempC.toDataURL('image/png')
}

function applyExtractSelection() {
  const resources = ensureExtractResources()
  if (!resources || !extractMaskCanvas || !extractMaskCtx) {
    return { error: 'Background layer not ready' }
  }

  if (!hasExtractSelection()) {
    return null
  }

  const { img } = resources
  
  const fgCanvas = document.createElement('canvas')
  fgCanvas.width = img.width
  fgCanvas.height = img.height
  const fgCtx = fgCanvas.getContext('2d')
  if (!fgCtx) return { error: 'Cannot create temporary canvas' }

  fgCtx.drawImage(img, 0, 0)
  fgCtx.globalCompositeOperation = 'destination-in'
  fgCtx.drawImage(extractMaskCanvas, 0, 0)
  
  const foregroundDataUrl = fgCanvas.toDataURL('image/png')

  const bgCanvas = document.createElement('canvas')
  bgCanvas.width = img.width
  bgCanvas.height = img.height
  const bgCtx = bgCanvas.getContext('2d')
  if (!bgCtx) return { error: 'Cannot create background canvas' }
  
  bgCtx.drawImage(img, 0, 0)
  
  bgCtx.globalCompositeOperation = 'destination-out'
  bgCtx.drawImage(extractMaskCanvas, 0, 0)
  
  bgCtx.globalCompositeOperation = 'source-over'
  const backgroundDataUrl = inpaintSimple(bgCtx, img.width, img.height) || img.src

  const extractMaskDataUrl = extractMaskCanvas.toDataURL('image/png')
  
  return { 
      foregroundDataUrl,
      backgroundDataUrl,
      extractMaskDataUrl
  }
}

function handlePathClick(coords: { x: number, y: number }, e: MouseEvent) {
  const layer = store.currentLayer
  if (!layer) return
  
  if (!layer.bezierPath) layer.bezierPath = []
  
  const hitIndex = findPathPointAt(coords)
  
  if (hitIndex >= 0) {
    selectedPathPoint = hitIndex
    isPathEditing = true
  } else {
    const centerX = store.project.width / 2
    const centerY = store.project.height / 2
    
    layer.bezierPath.push({
      x: coords.x - centerX,
      y: coords.y - centerY
    })
    
    if (layer.bezierPath.length >= 2) {
      layer.usePathAnimation = true
    }
    
    scheduleRender()
  }
}

function findPathPointAt(coords: { x: number, y: number }): number {
  const layer = store.currentLayer
  if (!layer || !layer.bezierPath) return -1
  
  const centerX = store.project.width / 2
  const centerY = store.project.height / 2
  const hitRadius = 10
  
  for (let i = 0; i < layer.bezierPath.length; i++) {
    const pt = layer.bezierPath[i]
    const dx = (pt.x + centerX) - coords.x
    const dy = (pt.y + centerY) - coords.y
    if (Math.sqrt(dx * dx + dy * dy) < hitRadius) {
      return i
    }
  }
  return -1
}

function updatePathPoint(coords: { x: number, y: number }) {
  const layer = store.currentLayer
  if (!layer || !layer.bezierPath || selectedPathPoint < 0) return
  
  const centerX = store.project.width / 2
  const centerY = store.project.height / 2
  
  layer.bezierPath[selectedPathPoint].x = coords.x - centerX
  layer.bezierPath[selectedPathPoint].y = coords.y - centerY
  
  scheduleRender()
}

function onMouseUp() {
  isDragging = false
  isMaskDrawing = false
  isExtractDrawing = false
  isPathEditing = false
  selectedPathPoint = -1
  isPanoOrbit = false
  isPanoPan = false
  isCameraPan = false
}

function onWheel(e: WheelEvent) {
  const delta = e.deltaY > 0 ? -0.05 : 0.05
  
  const isCameraWheel = store.project.pano_enable &&
    !store.maskMode.enabled && !store.extractMode.enabled && !store.pathMode.enabled &&
    (!store.currentLayer || e.ctrlKey || e.altKey)

  if (isCameraWheel) {
    const nextFov = Math.min(170, Math.max(10, (store.project.cam_fov || 90) + (delta > 0 ? 2 : -2)))
    store.setProject({ cam_fov: nextFov })
    store.setProjectKeyframe?.('cam_fov', store.currentTime, nextFov)
    scheduleRender()
    return
  }

  const camera3DEnabled = !!(store.project.cam_enable)
  const cameraReady = camera3DEnabled && !store.project.pano_enable &&
    !store.maskMode.enabled && !store.extractMode.enabled && !store.pathMode.enabled &&
    !store.currentLayer

  if (cameraReady && !store.currentLayer) {
    const currentZ = store.project.cam_pos_z || 0
    const step = 5
    const nextZ = currentZ + (delta > 0 ? step : -step)
    store.setProject({ cam_pos_z: nextZ })
    store.setProjectKeyframe?.('cam_pos_z', store.currentTime, nextZ)
    scheduleRender()
    return
  }

  if (!store.currentLayer) return

  const layer = store.currentLayer
  const props = getLayerProps(layer)
  const rotationStep = 2
  
  if (e.shiftKey && !e.ctrlKey && !e.altKey) {
    const newRotationX = props.rotationX + (delta > 0 ? rotationStep : -rotationStep)
    updateLayerWithKeyframes(layer, 'rotationX', newRotationX)
  } else if (e.ctrlKey && !e.shiftKey && !e.altKey) {
    const newRotationY = props.rotationY + (delta > 0 ? rotationStep : -rotationStep)
    updateLayerWithKeyframes(layer, 'rotationY', newRotationY)
  } else if (e.altKey && !e.shiftKey && !e.ctrlKey) {
    const newRotationZ = (props.rotationZ || props.rotation || 0) + (delta > 0 ? rotationStep : -rotationStep)
    updateLayerWithKeyframes(layer, 'rotationZ', newRotationZ)
  } else {
    const newScale = Math.max(0.1, Math.min(5, props.scale + delta))
    updateLayerWithKeyframes(layer, 'scale', newScale)
  }
  scheduleRender()
}

function onKeyDown(e: KeyboardEvent) {
  if (!store.currentLayer) return
  
  const step = e.shiftKey ? 10 : 1
  const layer = store.currentLayer
  const props = getLayerProps(layer)
  
  switch (e.key) {
    case 'ArrowLeft':
      updateLayerWithKeyframes(layer, 'x', props.x - step)
      scheduleRender()
      e.preventDefault()
      break
    case 'ArrowRight':
      updateLayerWithKeyframes(layer, 'x', props.x + step)
      scheduleRender()
      e.preventDefault()
      break
    case 'ArrowUp':
      updateLayerWithKeyframes(layer, 'y', props.y - step)
      scheduleRender()
      e.preventDefault()
      break
    case 'ArrowDown':
      updateLayerWithKeyframes(layer, 'y', props.y + step)
      scheduleRender()
      e.preventDefault()
      break
    case 'r':
    case 'R':
      updateLayerWithKeyframes(layer, 'x', 0)
      updateLayerWithKeyframes(layer, 'y', 0)
      updateLayerWithKeyframes(layer, 'scale', 1)
      updateLayerWithKeyframes(layer, 'rotation', 0)
      updateLayerWithKeyframes(layer, 'opacity', 1)
      scheduleRender()
      e.preventDefault()
      break
    case 'Delete':
    case 'Backspace':
      if (confirm('Delete current layer?')) {
        store.removeLayer(store.currentLayerIndex)
      }
      e.preventDefault()
      break
  }
}

defineExpose({
  clearExtractSelection,
  applyExtractSelection
})
</script>

<style scoped>
.canvas-preview {
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: visible;
  box-sizing: border-box;
  min-width: 0;
  min-height: 0;
  flex: 1 1 auto;
}

.canvas-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

canvas {
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
  cursor: move;
  outline: none;
  will-change: contents;
  transform: translateZ(0);
  image-rendering: -webkit-optimize-contrast;
  box-sizing: border-box;
  display: block;
  contain: layout style paint;
}

canvas:focus {
  box-shadow: 0 0 0 2px #3a7bc8, 0 4px 24px rgba(0, 0, 0, 0.5);
}

.canvas-info {
  position: relative;
  margin-top: 8px;
  margin-left: auto;
  margin-right: auto;
  width: fit-content;
  background: rgba(0, 0, 0, 0.8);
  color: #aaa;
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 4px;
  white-space: nowrap;
  z-index: 10;
  pointer-events: none;
  text-align: center;
}

.gpu-badge {
  background: linear-gradient(135deg, #00b894, #00cec9);
  color: #fff;
  font-size: 9px;
  font-weight: bold;
  padding: 2px 5px;
  border-radius: 3px;
  margin-right: 6px;
}
</style>
