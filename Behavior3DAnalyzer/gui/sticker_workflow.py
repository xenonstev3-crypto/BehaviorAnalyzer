"""Standalone Sticker test workflow."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.errors import DataContractError
from core.input_validation import validate_wide_csv
from experiments.sticker.analysis import StickerConfig, analyze_sticker, write_sticker_outputs
from experiments.sticker.visuals import write_3d_video, write_visuals


class StickerWorkflow(QWidget):
    """State-contained Sticker test workflow."""

    def __init__(self, return_home):
        super().__init__()
        self.return_home = return_home
        self.data: pd.DataFrame | None = None
        self.input_path: Path | None = None
        self.result = None
        self.coordinate_ready = False

        layout = QVBoxLayout(self)
        back = QPushButton("← 返回实验选择")
        back.clicked.connect(self.return_home)
        layout.addWidget(back, 0, Qt.AlignLeft)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._import_page(), "1. 导入数据")
        self.tabs.addTab(self._coordinate_page(), "2. 坐标准备")
        self.tabs.addTab(self._analysis_page(), "3. Sticker 分析")
        self.tabs.addTab(self._results_page(), "4. 结果与导出")
        layout.addWidget(self.tabs, 1)

    @staticmethod
    def _notice(text: str, color: str = "#374151") -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"padding: 10px; background: #f3f4f6; color: {color}; border-radius: 4px;"
        )
        return label

    def _import_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._notice(
            "请导入单个 trial 的三维宽表 CSV。"
            "", "#1e40af"
        ))
        form = QFormLayout()
        self.csv_path = QLineEdit()
        self.csv_path.setPlaceholderText("选择单一 trial 的原始宽表 CSV")
        choose_csv = QPushButton("选择 CSV")
        choose_csv.clicked.connect(self._select_csv)
        row = QHBoxLayout()
        row.addWidget(self.csv_path)
        row.addWidget(choose_csv)
        form.addRow("原始 CSV", row)

        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("选择独立结果目录；结果会分为 analysis / figures / video")
        choose_output = QPushButton("选择结果目录")
        choose_output.clicked.connect(self._select_output)
        row = QHBoxLayout()
        row.addWidget(self.output_dir)
        row.addWidget(choose_output)
        form.addRow("独立结果目录", row)
        layout.addLayout(form)

        self.import_status = self._notice("尚未导入。", "#6b7280")
        layout.addWidget(self.import_status)
        self.points_label = QLabel("识别到的完整 XYZ 点：—")
        self.points_label.setWordWrap(True)
        layout.addWidget(self.points_label)
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.preview, 1)
        return page

    def _coordinate_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._notice(
            "此步骤确认上游三维坐标的单位、帧率、关键点和质量检查。贴纸接触使用目标点与"
            "三维欧氏距离；同一个刚体坐标变换不会改变该距离。因此本期直接使用上游已标定"
            "坐标。若需为展示统一方向，请在上游完成"
            "有固定参考的标定后再导入。", "#7c2d12"
        ))
        self.coordinate_details = QPlainTextEdit()
        self.coordinate_details.setReadOnly(True)
        self.coordinate_details.setPlaceholderText("导入后会在此显示坐标单位、帧率和关键点。")
        layout.addWidget(self.coordinate_details, 1)
        button = QPushButton("确认使用此三维坐标进行 Sticker 分析")
        button.clicked.connect(self._confirm_coordinates)
        layout.addWidget(button)
        self.coordinate_status = self._notice("请先导入并验证 CSV。", "#6b7280")
        layout.addWidget(self.coordinate_status)
        return page

    def _analysis_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._notice(
            "持续接触由贴纸目标点与前爪等效应器的距离、最短持续时间和数据质量共同判定。"
            "“终止候选”只代表互动强度持续下降，不能单独证明贴纸已经脱落，必须结合视频复核。",
            "#7c2d12"
        ))
        form = QFormLayout()
        self.target = QLineEdit("nose_tip")
        self.effectors = QLineEdit("left_paw_tip, right_paw_tip")
        self.distance = QLineEdit("15.0")
        self.minimum = QSpinBox()
        self.minimum.setRange(1, 10000)
        self.minimum.setValue(3)
        self.sustain = QSpinBox()
        self.sustain.setRange(1, 100000)
        self.sustain.setValue(30)
        self.likelihood = QLineEdit("0.9")
        for label, field in (
            ("贴纸目标点", self.target),
            ("效应器点（逗号分隔）", self.effectors),
            ("接触距离阈值（坐标单位）", self.distance),
            ("最短接触帧数", self.minimum),
            ("终止候选持续帧数", self.sustain),
            ("最低置信度（留空则不限制）", self.likelihood),
        ):
            form.addRow(label, field)
        run = QPushButton("分析并写入事件明细")
        run.clicked.connect(self._analyse)
        form.addRow(run)
        layout.addLayout(form)

        self.analysis_status = self._notice("请先完成导入和坐标准备。", "#6b7280")
        layout.addWidget(self.analysis_status)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlaceholderText("分析摘要会显示在这里。")
        layout.addWidget(self.summary)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)
        return page

    def _results_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._notice(
            "所有导出仅写入你选择的结果目录，并分类为 analysis、figures、video；"
            "不会覆盖同名文件。", "#1e40af"
        ))
        self.result_status = self._notice("请先完成 Sticker 分析。", "#6b7280")
        layout.addWidget(self.result_status)
        self.result_summary = QPlainTextEdit()
        self.result_summary.setReadOnly(True)
        layout.addWidget(self.result_summary, 1)
        export = QPushButton("导出图表（PNG、PDF、SVG）和三维关键点视频（MP4）")
        export.clicked.connect(self._export_visuals)
        layout.addWidget(export)
        return page

    def _select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择贴纸实验 CSV", str(Path.home()), "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            data = pd.read_csv(path)
            contract = validate_wide_csv(data)
        except (OSError, pd.errors.ParserError, DataContractError) as error:
            self.data = None
            self.coordinate_ready = False
            self.import_status.setText("导入未通过：" + str(error))
            self.import_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")
            return

        self.data = data
        self.input_path = Path(path)
        self.coordinate_ready = False
        self.csv_path.setText(path)
        self.import_status.setText(
            f"导入成功：{len(data)} 帧，单位 {contract['coordinate_unit']}，fps {contract['fps']}。"
        )
        self.import_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
        self.points_label.setText("识别到的完整 XYZ 点：" + "、".join(contract["point_names"]))
        self.coordinate_details.setPlainText(
            "输入检查通过\n"
            f"坐标单位：{contract['coordinate_unit']}\n"
            f"帧率：{contract['fps']} fps\n"
            f"关键点：{', '.join(contract['point_names'])}\n\n"
            "将原始上游三维坐标保持不变进行距离分析；"
            "没有固定环境参考时，不会创建虚假的“重建”坐标。"
        )
        self._show_preview(data)
        if not self.output_dir.text().strip():
            self.output_dir.setText(str(Path(path).parent / "sticker_results"))

    def _select_output(self):
        path = QFileDialog.getExistingDirectory(
            self, "选择 Sticker 独立结果目录", self.output_dir.text() or str(Path.home())
        )
        if path:
            self.output_dir.setText(path)

    def _confirm_coordinates(self):
        if self.data is None:
            QMessageBox.warning(self, "尚未导入", "请先导入并通过 CSV 检查。")
            return
        self.coordinate_ready = True
        self.coordinate_status.setText(
            "坐标准备已确认：将保持上游三维坐标不变，并按记录的单位和帧率分析。"
        )
        self.coordinate_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")

    def _config(self) -> StickerConfig:
        minimum_likelihood = self.likelihood.text().strip()
        return StickerConfig(
            target_point=self.target.text().strip(),
            effector_points=tuple(
                point.strip() for point in self.effectors.text().split(",") if point.strip()
            ),
            contact_distance=float(self.distance.text()),
            min_contact_frames=self.minimum.value(),
            cessation_sustain_frames=self.sustain.value(),
            minimum_likelihood=float(minimum_likelihood) if minimum_likelihood else None,
        )

    def _analyse(self):
        if self.data is None or not self.coordinate_ready:
            QMessageBox.warning(self, "需要坐标准备", "请先导入 CSV，并在“坐标准备”页确认坐标。")
            return
        if not self.output_dir.text().strip():
            QMessageBox.warning(self, "需要结果目录", "请选择独立结果目录。")
            return
        try:
            self.result = analyze_sticker(self.data, self._config())
            paths = write_sticker_outputs(self._folder("analysis"), self.result)
            summary = self.result.summary
            text = "\n".join(
                f"{key}: {value}" for key, value in summary.items()
                if key not in {"config", "created_at_utc"}
            )
            text += f"\n\n事件明细：{paths['events']}\n逐帧质量：{paths['frames']}"
            self.summary.setPlainText(text)
            self.result_summary.setPlainText(text)
            self._show_events(self.result.events)
            self.analysis_status.setText("Sticker 分析完成。请复核事件明细以及终止候选对应的视频。")
            self.analysis_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
            self.result_status.setText("分析结果已就绪。可导出图表和三维关键点视频。")
            self.result_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
        except (ValueError, DataContractError, FileExistsError, OSError) as error:
            self.analysis_status.setText("未生成事件结果：" + str(error))
            self.analysis_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")

    def _export_visuals(self):
        if self.result is None or self.data is None:
            QMessageBox.warning(self, "尚无分析结果", "请先完成 Sticker 分析。")
            return
        try:
            figures = write_visuals(self._folder("figures"), self.data, self.result)
            video = write_3d_video(self._folder("video"), self.data, self.result)
            self.result_status.setText(
                f"可视化已导出：PNG {figures['png']}；PDF {figures['pdf']}；"
                f"SVG {figures['svg']}；MP4 {video}"
            )
            self.result_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
        except (FileExistsError, OSError, RuntimeError, ValueError) as error:
            self.result_status.setText("未导出可视化：" + str(error))
            self.result_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")

    def _folder(self, category: str) -> Path:
        return Path(self.output_dir.text().strip()) / category

    def _show_preview(self, data: pd.DataFrame):
        view = data.head(20)
        self.preview.setRowCount(len(view))
        self.preview.setColumnCount(len(view.columns))
        self.preview.setHorizontalHeaderLabels(list(view.columns))
        for row_index, (_, row) in enumerate(view.iterrows()):
            for column_index, value in enumerate(row):
                self.preview.setItem(row_index, column_index, QTableWidgetItem(str(value)))
        self.preview.resizeColumnsToContents()

    def _show_events(self, events: pd.DataFrame):
        self.table.setRowCount(len(events))
        self.table.setColumnCount(len(events.columns))
        self.table.setHorizontalHeaderLabels(list(events.columns))
        for row_index, (_, row) in enumerate(events.iterrows()):
            for column_index, value in enumerate(row):
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
