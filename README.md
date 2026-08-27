# CD-image

面向 Codex 的智能图片生成与编辑 Skill，支持文生图、参考图编辑，
以及 `1K`、`2K`、`4K` 和自定义尺寸图片输出。

客户端会使用当前 API key 请求中转的 `/v1/models`，自动识别该分组可用的
图片模型并选择对应访问通道：

- `gemini-*-image` 模型自动使用 Gemini 原生通道。
- `gpt-image-*` 模型自动使用 Image2 通道。

如需固定模型或通道，可在命令中传入 `--model <model-name>` 或
`--channel <gemini|image2>`。

## 安装

1. 下载 [CD-image.zip](https://github.com/jianglei1111/cd-image/raw/refs/heads/main/CD-image.zip)。
2. 把下载好的 ZIP 文件拖进 Codex 对话。
3. 告诉 Codex：`请安装这个 Skill。`

安装完成后，即可在 Codex 中使用 `$cd-image` 自动选择可用模型生成或编辑图片。

## 示例图

下面三张西部牛仔风格的 Tom 海报使用相同主题生成，Skill 会根据当前 API key
自动发现可用模型并选择对应访问通道。

### GPT Image 2

由 `gpt-image-2` 通过 Image2 通道生成，尺寸为 `1024 × 1536`：

![GPT Image 2 生成的 Tom 西部牛仔海报](tom-western-gpt-image-2.png)

### Gemini 3.1 Flash Image

由 `gemini-3.1-flash-image` 通过 Gemini 原生通道生成，尺寸为 `1696 × 2528`：

![Gemini 3.1 Flash Image 生成的 Tom 西部牛仔海报](tom-western-gemini-3-1-flash.jpg)

### Gemini 3 Pro Image

由 `gemini-3-pro-image` 通过 Gemini 原生通道生成，尺寸为 `1696 × 2528`：

![Gemini 3 Pro Image 生成的 Tom 西部牛仔海报](tom-western-gemini-3-pro.jpg)
