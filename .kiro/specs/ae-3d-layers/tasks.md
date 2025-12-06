# Implementation Plan

- [x] 1. Backend: Implement 3D Transform Engine









  - [x] 1.1 Create Transform3D class with matrix builders



    - Implement `build_model_matrix(x, y, z, rotX, rotY, rotZ, scaleX, scaleY, scaleZ, anchorX, anchorY)`
    - Implement `build_view_matrix(cam_pos_x, cam_pos_y, cam_pos_z, yaw, pitch, roll)`
    - Implement `build_projection_matrix(fov, aspect, near, far)`
    - _Requirements: 1.3, 1.4, 2.2, 2.3, 2.4, 5.1_

  - [ ]* 1.2 Write property test for model matrix
    - **Property 2: Position Changes Update Transform**
    - **Property 3: Rotation Around Anchor Point**
    - **Validates: Requirements 1.3, 1.4, 5.1**

  - [ ]* 1.3 Write property test for view matrix
    - **Property 4: Camera View Matrix Correctness**
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 1.4 Write property test for projection matrix
    - **Property 5: FOV Affects Projection**
    - **Validates: Requirements 2.4**


- [x] 2. Backend: Update AEAnimation node for 3D rendering




  - [x] 2.1 Extend layer data model with 3D properties


    - Add is3D, rotationX, rotationY, rotationZ, scaleX, scaleY, scaleZ, anchorX, anchorY to _decode_layers
    - Update _get_value to support new properties
    - _Requirements: 1.1, 1.2, 4.1_

  - [x] 2.2 Implement Z-depth sorting in execute method



    - Sort layers by transformed Z position before rendering
    - Recalculate sort order for each frame
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 2.3 Write property test for Z-depth sorting
    - **Property 6: Z-Depth Sorting Consistency**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x] 2.4 Implement perspective projection rendering


    - Apply MVP matrix to layer corners
    - Use cv2.getPerspectiveTransform and cv2.warpPerspective
    - _Requirements: 8.1, 8.2_

  - [ ]* 2.5 Write property test for scale transform
    - **Property 7: Scale Transform Around Anchor**
    - **Validates: Requirements 4.2, 4.3**

- [x] 3. Checkpoint - Ensure all backend tests pass


  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Backend: Keyframe interpolation for 3D properties



  - [x] 4.1 Extend _get_value to handle all 3D properties


    - Support rotationX, rotationY, rotationZ keyframes
    - Support scaleX, scaleY, scaleZ keyframes
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 4.2 Write property test for keyframe interpolation
    - **Property 8: Keyframe Interpolation Correctness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [x] 5. Frontend: Add 3D layer controls to Timeline UI



  - [x] 5.1 Extend layer store with 3D properties



    - Add is3D toggle, rotationX/Y/Z, scaleX/Y/Z, anchorX/Y fields
    - Initialize defaults when 3D mode enabled
    - _Requirements: 1.1, 1.2, 4.1_

  - [x] 5.2 Create 3D property controls in layer panel



    - Add position X/Y/Z sliders
    - Add rotation X/Y/Z sliders
    - Add scale X/Y/Z sliders
    - Add anchor X/Y inputs
    - _Requirements: 1.1, 1.2, 4.1, 5.1_

- [x] 6. Frontend: Implement CSS 3D preview engine


  - [x] 6.1 Create buildCSSTransform function


    - Generate translate3d, rotateX, rotateY, rotateZ, scale3d string
    - Apply transforms in correct order (translate → rotate → scale)
    - _Requirements: 7.2, 7.3_

  - [ ]* 6.2 Write property test for CSS transform generation
    - **Property 9: CSS Transform String Generation**
    - **Validates: Requirements 7.2, 7.3**

  - [x] 6.3 Apply CSS transforms to layer preview elements

    - Set transform-style: preserve-3d on container
    - Apply perspective to parent element
    - Update transforms on property change
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 7. Frontend: Camera controls


  - [x] 7.1 Add camera control panel


    - Position X/Y/Z sliders
    - Rotation yaw/pitch/roll sliders
    - FOV slider
    - _Requirements: 2.1_

  - [x] 7.2 Apply camera transform to preview container

    - Update container perspective based on FOV
    - Apply inverse camera transform to scene
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 8. Checkpoint - Ensure all frontend tests pass

  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Integration: Frontend-Backend consistency

  - [x] 9.1 Create shared matrix computation logic

    - Ensure same transform order in both frontend and backend
    - Document coordinate system conventions
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 9.2 Write property test for frontend-backend equivalence
    - **Property 10: Frontend-Backend Matrix Equivalence**
    - **Validates: Requirements 8.1, 8.2, 8.3**


- [x] 10. Final Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.
