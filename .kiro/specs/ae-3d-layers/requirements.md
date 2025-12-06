# Requirements Document

## Introduction

实现类似 Adobe After Effects 的真正 3D 图层系统，支持图层在 3D 空间中的位置、旋转、缩放变换，以及 3D 摄像机控制。用户可以在前端实时预览 3D 效果，后端渲染时也能正确处理 3D 变换。

## Glossary

- **3D Layer (3D 图层)**: 在三维空间中具有 X、Y、Z 位置和 X、Y、Z 旋转的图层
- **Camera (摄像机)**: 定义观察 3D 场景的视角，包含位置、旋转、FOV 等属性
- **Anchor Point (锚点)**: 图层变换的中心点，旋转和缩放围绕此点进行
- **Perspective (透视)**: 3D 投影中近大远小的视觉效果
- **Z-Depth (Z 深度)**: 图层在 Z 轴上的位置，决定前后关系和透视缩放
- **Homogeneous Coordinates (齐次坐标)**: 用于 3D 变换的 4D 坐标系统
- **Projection Matrix (投影矩阵)**: 将 3D 坐标转换为 2D 屏幕坐标的矩阵

## Requirements

### Requirement 1

**User Story:** As a user, I want to enable 3D mode for individual layers, so that I can position and rotate them in 3D space.

#### Acceptance Criteria

1. WHEN a user enables 3D mode for a layer THEN the System SHALL display X, Y, Z position controls for that layer
2. WHEN a user enables 3D mode for a layer THEN the System SHALL display X, Y, Z rotation controls (rotationX, rotationY, rotationZ)
3. WHEN a user modifies 3D position values THEN the System SHALL update the layer preview in real-time
4. WHEN a user modifies 3D rotation values THEN the System SHALL apply rotation around the layer's anchor point

### Requirement 2

**User Story:** As a user, I want to control a 3D camera, so that I can view my composition from different angles.

#### Acceptance Criteria

1. WHEN a user enables camera mode THEN the System SHALL provide camera position controls (cam_pos_x, cam_pos_y, cam_pos_z)
2. WHEN a user adjusts camera position THEN the System SHALL update the view of all 3D layers accordingly
3. WHEN a user adjusts camera rotation (yaw, pitch, roll) THEN the System SHALL rotate the view around the camera's position
4. WHEN a user adjusts camera FOV THEN the System SHALL change the perspective projection strength

### Requirement 3

**User Story:** As a user, I want layers to be rendered with correct depth ordering, so that closer layers appear in front of farther layers.

#### Acceptance Criteria

1. WHEN multiple 3D layers exist at different Z positions THEN the System SHALL render layers from back to front based on their Z depth
2. WHEN a layer's Z position changes during animation THEN the System SHALL dynamically re-sort the rendering order
3. WHEN layers intersect in 3D space THEN the System SHALL use painter's algorithm based on layer center Z position

### Requirement 4

**User Story:** As a user, I want to scale layers in 3D space, so that I can create depth effects and size animations.

#### Acceptance Criteria

1. WHEN a user enables 3D mode for a layer THEN the System SHALL provide separate X, Y, Z scale controls (scaleX, scaleY, scaleZ)
2. WHEN a user adjusts scaleX or scaleY THEN the System SHALL scale the layer along that axis relative to the anchor point
3. WHEN a user adjusts scaleZ THEN the System SHALL apply depth scaling that affects the layer's apparent size based on Z position
4. WHEN scale values are animated with keyframes THEN the System SHALL interpolate scale values smoothly between keyframes

### Requirement 5

**User Story:** As a user, I want to set anchor points for layers, so that rotations and scales happen around the correct center.

#### Acceptance Criteria

1. WHEN a user sets anchor point values THEN the System SHALL use those values as the rotation/scale center
2. WHEN anchor point is (0, 0) THEN the System SHALL rotate around the layer's center
3. WHEN anchor point is offset THEN the System SHALL offset the rotation center accordingly

### Requirement 6

**User Story:** As a user, I want to animate 3D properties with keyframes, so that I can create smooth 3D animations.

#### Acceptance Criteria

1. WHEN a user adds keyframes for 3D position THEN the System SHALL interpolate position values between keyframes
2. WHEN a user adds keyframes for 3D rotation THEN the System SHALL interpolate rotation values between keyframes
3. WHEN a user adds keyframes for 3D scale THEN the System SHALL interpolate scale values between keyframes
4. WHEN rendering animation frames THEN the System SHALL apply interpolated 3D transforms for each frame

### Requirement 7

**User Story:** As a user, I want real-time 3D preview in the frontend, so that I can see changes immediately without waiting for backend rendering.

#### Acceptance Criteria

1. WHEN a user adjusts 3D layer properties THEN the Frontend SHALL update the preview within 16ms (60fps target)
2. WHEN a user scrubs the timeline THEN the Frontend SHALL display the correct 3D state for that frame
3. WHEN the frontend renders 3D preview THEN the Frontend SHALL use CSS 3D transforms for hardware-accelerated rendering

### Requirement 8

**User Story:** As a user, I want the backend renderer to produce the same 3D result as the frontend preview, so that my final output matches what I see during editing.

#### Acceptance Criteria

1. WHEN the backend renders a frame THEN the System SHALL apply the same 3D transformation matrix as the frontend
2. WHEN the backend renders 3D layers THEN the System SHALL use perspective projection matching the camera FOV
3. WHEN the backend composites layers THEN the System SHALL respect Z-depth ordering and apply correct alpha blending

