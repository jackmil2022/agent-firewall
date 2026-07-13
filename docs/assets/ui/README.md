# Agent Firewall UI Image Generation

本目录保存 Agent Firewall 的 UI 设计图、生成任务和总览图。

## Deliverables

- 25 张主屏：P01-P25，覆盖 PRD 0.1-0.3。
- 8 张状态板：S01-S08，覆盖 20 个异常、等待和完成状态。
- 1 张 `contact-sheet.png`：全部资产的缩略总览，图片生成后由本地 Pillow 命令拼接。

完整文件名与逐图提示词见 [imagegen-prompts.jsonl](imagegen-prompts.jsonl)，页面映射见 [UI 设计说明](../../ui-design-agent-orchestration.md#9-complete-screen-matrix)。

## Shared Prompt

```text
Use case: ui-mockup.
Asset type: shippable desktop application screen.
Product: Agent Firewall, a desktop platform for importing and orchestrating existing Agents, Skills, and MCP Tools.
Audience: business workflow creators and platform operators.
Style: precision automation workbench; quiet industrial product UI; realistic product screenshot, not concept art.
Visual system: light canvas #F2F4F1, white surfaces, charcoal #171B18 text, thin #D4DBD5 dividers, teal #177E67 primary action, blue Agent, green Skill, amber Tool, restrained coral correction/failure; 4-6px radius; dense Source Sans 3 and Noto Sans SC-like typography; no gradients or glass effects.
Composition: straight-on full-window 1536x960 desktop screenshot; 52px top bar; 56px global navigation; stable panels; no browser or device frame.
Constraints: render requested Chinese labels verbatim; no pseudo-text, clipped text, overlapping panels, raw JSON in primary paths, watermark, marketing hero, nested card wall, purple theme, decorative blobs or oversized headings.
```

## Generation

Mode: user-approved CLI fallback using the installed `imagegen` skill CLI, model `gpt-image-2`, `1536x960`, medium quality. Medium is used for the first complete batch; only failed or illegible screens are regenerated at high quality.

Prerequisites:

```bash
export OPENAI_API_KEY="..."
```

Batch command:

```bash
.venv/bin/python "$HOME/.codex/skills/.system/imagegen/scripts/image_gen.py" generate-batch \
  --input docs/assets/ui/imagegen-prompts.jsonl \
  --out-dir docs/assets/ui \
  --concurrency 3 \
  --use-case ui-mockup \
  --style "precision automation workbench; quiet industrial desktop product UI; light canvas, white surfaces, thin dividers, teal actions, blue Agent, green Skill, amber Tool, restrained coral failures" \
  --composition "straight-on full-window 1536x960 desktop screenshot with stable panels and no device frame" \
  --constraints "readable verbatim Chinese labels; no pseudo-text, clipping, overlap, watermark, card wall, gradients, glass, purple theme or decorative blobs"
```

Current status: `P01` has been generated and visually checked. Per product direction, image generation for the remaining screens is intentionally skipped. The page matrix and prompt manifest remain as the UI handoff source of truth.

如果只有少数图片失败，应从 manifest 筛出对应任务单独重跑，不要用 `--force` 重生成完整批次。

## Contact Sheet

33 张 PNG 生成完成后执行：

```bash
.venv/bin/python - <<'PY'
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw

root = Path("docs/assets/ui")
jobs = [json.loads(line) for line in (root / "imagegen-prompts.jsonl").read_text().splitlines()]
files = [root / job["out"] for job in jobs]
cell_w, cell_h, cols = 336, 232, 4
rows = math.ceil(len(files) / cols)
sheet = Image.new("RGB", (cell_w * cols, cell_h * rows), "#f2f4f1")
draw = ImageDraw.Draw(sheet)
for index, path in enumerate(files):
    image = Image.open(path).convert("RGB")
    image.thumbnail((320, 200), Image.Resampling.LANCZOS)
    x = (index % cols) * cell_w + 8
    y = (index // cols) * cell_h + 8
    sheet.paste(image, (x, y))
    draw.text((x, y + 204), path.name, fill="#171b18")
sheet.save(root / "contact-sheet.png")
PY
```
