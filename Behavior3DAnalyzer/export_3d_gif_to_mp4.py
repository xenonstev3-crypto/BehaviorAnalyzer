"""使用 Python 将已核对的三维关键点 GIF 转为 H.264 MP4；不覆盖现有输出。"""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio


def main() -> None:
    # 明确使用本项目约定的 Windows 桌面路径，避免不同 Python 启动方式改变 Path.home()。
    output_dir = Path(r"C:\Users\33913\Desktop\Behavior3DAnalyzer_10s_demo_outputs")
    source = output_dir / "Video_1_3D_reconstructed_keypoints.gif"
    destination = output_dir / "Video_1_3D_reconstructed_keypoints.mp4"
    if not source.exists():
        raise FileNotFoundError(f"找不到源动画：{source}")
    if destination.exists():
        raise FileExistsError(f"拒绝覆盖已有视频：{destination}")
    reader = imageio.get_reader(source)
    with imageio.get_writer(destination, fps=10, codec="libx264", quality=8, macro_block_size=1) as writer:
        for frame in reader:
            writer.append_data(frame)
    reader.close()
    print(destination)


if __name__ == "__main__":
    main()
