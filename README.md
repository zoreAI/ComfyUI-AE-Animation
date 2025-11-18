# ComfyUI-AE-Animation

ComfyUI的After Effects风格动画时间轴节点，支持关键帧动画、图层管理、Mask编辑和背景提取功能。

## 功能特性

### 🎬 核心功能
- **时间轴编辑器**：可视化关键帧动画编辑
- **多图层管理**：背景层 + 多个前景层
- **关键帧动画**：位置、缩放、旋转、透明度动画
- **实时预览**：Canvas实时渲染预览

### 🎨 高级功能
- **Mask画笔**：自定义图层透明度遮罩
- **贝塞尔路径**：路径动画和运动轨迹
- **背景提取（Extract）**：画笔涂抹提取背景区域，自动模糊背景并创建新前景层
- **图层排序**：上移/下移/置顶/置底

### 🖼️ 背景模式
- **Fit**：保持宽高比，完整显示
- **Fill**：保持宽高比，填充画布
- **Stretch**：拉伸填充

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wallen0322/ComfyUI-AE-Animation.git
# 重启ComfyUI
```

## 使用方法

### 基础工作流

```
LoadImage (背景) → AEAnimationCore.background_image
LoadImage (前景) → AEAnimationCore.foreground_images (可选，支持批量)
AEAnimationCore.animation → AERender.animation
AERender.frames → PreviewImage / SaveImage
AERender.mask_frames → 输出Mask通道
```

### AEAnimationCore节点

**输入**：
- `width`, `height`：项目尺寸（默认512x512）
- `fps`：帧率（默认30）
- `total_frames`：总帧数（默认150）
- `mask_expansion`：Mask扩展/收缩（-10到10）
- `mask_feather`：Mask羽化（0到20）
- `background_image`：背景图片（可选）
- `foreground_images`：前景图片（可选，支持批量输入）

**输出**：
- `animation`：动画数据（JSON字符串）

### AERender节点

**输入**：
- `animation`：来自AEAnimationCore的动画数据
- `start_frame`：开始帧（默认0）
- `end_frame`：结束帧（-1表示全部）

**输出**：
- `frames`：渲染的图像序列（IMAGE）
- `mask_frames`：前景遮罩序列（MASK）

## 时间轴操作

### 图层操作

1. **选择图层**：下拉菜单选择当前图层
2. **调整属性**：X, Y, Scale, Rotation, Opacity, Mask Size
3. **图层排序**：
   - `↑` 上移一层
   - `↓` 下移一层
   - `⇈` 置于顶层
   - `⇊` 置于底层

### 关键帧动画

1. **添加关键帧**：调整时间滑块到目标时间 → 调整属性 → 点击 `◆` 添加
2. **删除关键帧**：点击时间轴上的关键帧标记 → 点击 `✕` 删除
3. **清除所有**：点击 `ALL` 清除当前图层所有关键帧
4. **播放预览**：点击 `▶` 播放，`■` 停止

### Mask功能

1. 选择前景图层
2. 点击 `🖌 Mask` 启用Mask模式
3. 调整笔刷大小
4. 在画布上涂抹（黑色=透明，白色=不透明）
5. 按住Shift或右键擦除
6. 点击 `✓ Apply Mask` 应用

### 贝塞尔路径

1. 选择图层
2. 点击 `📍 Path` 创建路径
3. 在画布上点击4个控制点（起点、控制点1、控制点2、终点）
4. 拖动点调整路径形状
5. 点击 `✓ Apply` 生成路径关键帧动画

### 背景提取（Extract）⭐

这是本节点的特色功能，可以从背景中提取部分区域并创建新的前景层：

1. **准备**：确保已加载背景图层
2. **启动Extract**：点击 `✂ Extract` 按钮
3. **涂抹选区**：
   - 用画笔在背景上涂抹要提取的区域
   - 调整笔刷大小（10-100）
   - 按住Shift或右键擦除错误涂抹
4. **选择模糊类型**：
   - **高斯模糊**：均匀模糊
   - **径向模糊**：从中心向外模糊（更自然）
5. **应用提取**：点击 `✓ Extract Region`

**提取效果**：
- ✅ 背景的选中区域自动应用最大强度模糊
- ✅ 选中的内容创建为新的前景层（extracted_X）
- ✅ 新图层可以独立调整位置、缩放、旋转等
- ✅ 可以添加关键帧实现动画效果
- ✅ 支持多次提取创建多个图层

**应用场景**：
- 人物抠图后对原背景进行背景虚化
- 提取背景的某个元素单独动画
- 景深效果（前景清晰，背景模糊）

## 技术特性

### 数据持久化
- 所有图层属性、关键帧、Mask、路径数据自动保存
- 工作流保存后重新加载可恢复所有状态
- Extract图层及其修改完整保存

### 性能优化
- Debounce机制减少不必要的保存操作
- requestAnimationFrame优化渲染性能
- 图片缓存减少重复加载

### 批量图片支持
- 前景图片输入支持4D张量 `[B, H, W, C]`
- 自动拆分为多个图层
- 每个图层可独立动画

## 快捷键

- **画布拖拽**：鼠标左键拖动图层
- **缩放图层**：鼠标滚轮
- **Mask擦除**：Shift + 鼠标左键 或 鼠标右键
- **Extract擦除**：Shift + 鼠标左键 或 鼠标右键

## 注意事项

1. **项目尺寸**：建议与背景图片尺寸相同或成比例
2. **图层数量**：前景图层数量 = foreground_images的批次数 + Extract创建的图层
3. **Mask分辨率**：Mask会自动缩放到图层原始尺寸
4. **Extract图层**：创建后会自动缩放到项目尺寸，scale=1即为全屏显示

## 更新日志

### v1.0.0
- ✅ 核心动画时间轴功能
- ✅ 多图层管理
- ✅ 关键帧动画
- ✅ Mask画笔编辑
- ✅ 贝塞尔路径动画
- ✅ 背景提取功能（Extract）
- ✅ 图层排序功能
- ✅ 批量前景图片支持
- ✅ 完整的数据持久化
- ✅ WebSocket实时预览

## 常见问题

**Q: Extract的图层为什么看起来很小？**  
A: Extract图层已自动缩放到项目尺寸，scale=1表示全屏。如果看起来小，请检查项目尺寸设置。

**Q: 如何让Extract的图层居中显示？**  
A: Extract图层默认x=0, y=0（画布中心）。如需调整，使用X/Y输入框或直接拖拽。

**Q: 能否多次Extract？**  
A: 可以！每次Extract会创建extracted_0, extracted_1...等独立图层，互不影响。

**Q: 关键帧动画不生效？**  
A: 确保在不同时间点添加了至少2个关键帧，并且属性值有变化。

**Q: Mask如何使用？**  
A: 黑色区域为透明，白色区域为不透明。使用画笔涂抹后点击Apply Mask应用。

## 许可证

MIT License

## 作者

wallen0322

## 贡献

欢迎提交Issue和PR！

## 致谢

感谢 [jtydhr88](https://github.com/jtydhr88) 柯基大佬指点！

时间轴灵感来自：[vanilla-threejs-project](https://github.com/fulopkovacs/vanilla-threejs-project)

感恩！

---

**享受创作动画的乐趣！** 🎬✨
