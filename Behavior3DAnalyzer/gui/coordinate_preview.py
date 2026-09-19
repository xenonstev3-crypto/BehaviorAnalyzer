"""不依赖额外绘图库的二维顶视/侧视预览。"""

from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CoordinatePreview(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._points: np.ndarray | None = None
        self.setMinimumHeight(240)

    def set_data(self, df: pd.DataFrame | None, *, reconstructed: bool = False) -> None:
        if df is None:
            self._points = None
            self.update()
            return
        suffix = "_reconstructed_x" if reconstructed else "_x"
        prefixes = sorted({column[: -len(suffix)] for column in df.columns if column.endswith(suffix)})
        xyz = []
        for prefix in prefixes:
            columns = ([f"{prefix}_reconstructed_x", f"{prefix}_reconstructed_y", f"{prefix}_reconstructed_z"] if reconstructed else [f"{prefix}_x", f"{prefix}_y", f"{prefix}_z"])
            if all(column in df.columns for column in columns):
                values = df.loc[:, columns].apply(pd.to_numeric, errors="coerce").to_numpy(float)
                xyz.append(values[:100])
        self._points = np.vstack(xyz) if xyz else None
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#fbfcfe"))
        painter.setPen(QColor("#243447"))
        painter.drawText(10, 20, self._title)
        area = self.rect().adjusted(20, 35, -20, -20)
        painter.setPen(QPen(QColor("#d0d7de"), 1))
        painter.drawRect(area)
        if self._points is None:
            painter.setPen(QColor("#6b7280"))
            painter.drawText(area, Qt.AlignCenter, "载入数据后显示前 100 帧的点位")
            return
        points = self._points[np.isfinite(self._points).all(axis=1)]
        if not len(points):
            painter.drawText(area, Qt.AlignCenter, "没有可绘制的完整坐标")
            return
        # 左为顶视 X/Y，右为侧视 X/Z。
        for index, (horizontal, vertical, label) in enumerate(((0, 1, "顶视 X/Y"), (0, 2, "侧视 X/Z"))):
            half = area.width() // 2
            sub = area.adjusted(index * half, 0, -(1 - index) * half, 0)
            values = points[:, [horizontal, vertical]]
            minimum, maximum = values.min(axis=0), values.max(axis=0)
            span = np.maximum(maximum - minimum, 1e-6)
            normalized = (values - minimum) / span
            painter.setPen(QColor("#6b7280")); painter.drawText(sub.adjusted(5, 5, -5, -5), Qt.AlignTop | Qt.AlignLeft, label)
            painter.setPen(QPen(QColor("#2563eb"), 3))
            for x, y in normalized:
                px = sub.left() + 8 + x * max(1, sub.width() - 16)
                py = sub.bottom() - 8 - y * max(1, sub.height() - 30)
                painter.drawPoint(int(px), int(py))
