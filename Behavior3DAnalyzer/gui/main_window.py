"""阶段 2：导入验证与 session-level 坐标重建界面。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QCheckBox, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QPlainTextEdit, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.errors import DataContractError, ReconstructionError
from core.input_validation import validate_wide_csv
from core.reconstruct_coordinates import (
    reconstruction_from_environment_markers,
    reconstruction_from_metadata,
    reconstruction_from_perimeter_points,
    write_reconstruction_outputs,
)
from experiments.cylinder.analysis import CylinderConfig, analyze_cylinder, load_literature_common_preset, write_cylinder_outputs
from experiments.cylinder.reporting import write_report_bundle
from experiments.cylinder.publication_visuals import write_3d_keypoint_video, write_publication_figure
from .coordinate_preview import CoordinatePreview


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.df: pd.DataFrame | None = None
        self.metadata: dict = {}
        self.input_path: Path | None = None
        self.transformed: pd.DataFrame | None = None
        self.transform_record: dict | None = None
        self.analysis_result = None
        self.setWindowTitle("Behavior3D Analyzer — Cylinder 全流程原型")
        self.resize(1200, 760)
        self._build_ui()

    def _build_ui(self):
        tabs = QTabWidget(); self.setCentralWidget(tabs)
        tabs.addTab(self._import_page(), "1. 导入数据")
        tabs.addTab(self._reconstruction_page(), "2. 重建坐标系")
        tabs.addTab(self._analysis_page(), "3. Cylinder 分析")
        tabs.addTab(self._results_page(), "4. 结果与导出")

    def _notice(self, text: str, color: str = "#374151"):
        label = QLabel(text); label.setWordWrap(True); label.setStyleSheet(f"padding: 10px; background: #f3f4f6; color: {color}; border-radius: 4px;")
        return label

    def _import_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(self._notice("科学限制：若 CSV/metadata 没有圆桶固定参考（底面圆心、竖直方向、底面 X 方向），软件不能可靠重建，也不会用动物平均位置猜测圆心。", "#9a3412"))
        row = QHBoxLayout(); self.csv_path = QLineEdit(); self.csv_path.setPlaceholderText("选择单一 trial 的原始宽表 CSV")
        choose_csv = QPushButton("选择 CSV"); choose_csv.clicked.connect(self._select_csv); row.addWidget(self.csv_path); row.addWidget(choose_csv); layout.addLayout(row)
        row = QHBoxLayout(); self.metadata_path = QLineEdit(); self.metadata_path.setPlaceholderText("可选：选择 trial_metadata.json")
        choose_meta = QPushButton("选择 metadata"); choose_meta.clicked.connect(self._select_metadata); row.addWidget(self.metadata_path); row.addWidget(choose_meta); layout.addLayout(row)
        self.import_status = self._notice("尚未导入。", "#6b7280"); layout.addWidget(self.import_status)
        self.points_label = QLabel("识别到的点：—"); self.points_label.setWordWrap(True); layout.addWidget(self.points_label)
        self.preview_table = QTableWidget(); self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.preview_table, 1)
        return page

    def _reconstruction_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(self._notice("默认仅执行 session-level 变换。固定环境标记若漂移过大，程序会停止并提示检查质量；frame-level 变换将在后续阶段实现。", "#1e40af"))
        body = QGridLayout(); layout.addLayout(body, 1)
        controls = QFrame(); controls.setFrameShape(QFrame.StyledPanel); form = QFormLayout(controls)
        self.method = QComboBox(); self.method.addItems(["A. metadata 直接参考", "B. CSV 固定环境标记", "C. 底面圆周点拟合"]); form.addRow("参考来源", self.method)
        self.bottom_marker = QLineEdit("cylinder_bottom_center"); form.addRow("底面圆心标记", self.bottom_marker)
        self.top_marker = QLineEdit("cylinder_top_center"); form.addRow("桶顶中心标记", self.top_marker)
        self.x_marker = QLineEdit("x_axis_marker"); form.addRow("X 方向标记", self.x_marker)
        self.max_drift = QLineEdit("1.0"); form.addRow("最大标记漂移", self.max_drift)
        self.perimeter = QLineEdit("perimeter_a, perimeter_b, perimeter_c"); form.addRow("圆周标记（逗号分隔）", self.perimeter)
        self.vertical_hint = QLineEdit("[0, 0, 1]"); form.addRow("多点拟合 +Z 参考", self.vertical_hint)
        self.radius = QLineEdit("100.0"); form.addRow("声明圆桶半径", self.radius)
        self.plane_residual = QLineEdit("1.0"); form.addRow("最大平面残差", self.plane_residual)
        self.circle_residual = QLineEdit("1.0"); form.addRow("最大圆拟合残差", self.circle_residual)
        self.output_dir = QLineEdit(); choose_output = QPushButton("选择结果目录"); choose_output.clicked.connect(self._select_output_dir)
        output_row = QHBoxLayout(); output_row.addWidget(self.output_dir); output_row.addWidget(choose_output); form.addRow("独立结果目录", output_row)
        run = QPushButton("验证参考并生成重建结果"); run.clicked.connect(self._run_reconstruction); form.addRow(run)
        body.addWidget(controls, 0, 0)
        visual = QWidget(); visual_layout = QVBoxLayout(visual); self.raw_preview = CoordinatePreview("原始坐标预览"); self.new_preview = CoordinatePreview("重建坐标预览")
        visual_layout.addWidget(self.raw_preview); visual_layout.addWidget(self.new_preview); body.addWidget(visual, 0, 1)
        self.reconstruction_status = self._notice("请先在“导入数据”页载入并通过验证的 CSV。", "#6b7280"); layout.addWidget(self.reconstruction_status)
        return page

    def _analysis_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(self._notice("只分析本窗口刚生成的重建坐标。接近桶壁只是候选，仍会经过高度、质量、持续时间和双侧窗口规则；“文献常用预设”并非唯一国际标准。", "#7c2d12"))
        form = QFormLayout()
        self.analysis_preset = QComboBox(); self.analysis_preset.addItems(["文献常用预设", "自定义规则"]); self.analysis_preset.currentIndexChanged.connect(self._load_preset_into_ui); form.addRow("规则来源", self.analysis_preset)
        self.left_paw = QLineEdit(); form.addRow("左前爪点名", self.left_paw)
        self.right_paw = QLineEdit(); form.addRow("右前爪点名", self.right_paw)
        self.analysis_radius = QLineEdit(); form.addRow("圆桶半径", self.analysis_radius)
        self.wall_tolerance = QLineEdit(); form.addRow("距壁容许距离", self.wall_tolerance)
        self.contact_min_z = QLineEdit(); form.addRow("触壁最低高度", self.contact_min_z)
        self.contact_max_z = QLineEdit(); form.addRow("触壁最高高度", self.contact_max_z)
        self.min_contact_frames = QLineEdit(); form.addRow("最短持续帧数", self.min_contact_frames)
        self.bilateral_window = QLineEdit(); form.addRow("双侧配对时间窗（帧）", self.bilateral_window)
        self.minimum_likelihood = QLineEdit(); form.addRow("最低置信度（留空则不限制）", self.minimum_likelihood)
        self.only_rearing = QCheckBox("仅在 rearing 期间计入"); form.addRow(self.only_rearing)
        self.rearing_point = QLineEdit(); form.addRow("rearing 身体点", self.rearing_point)
        self.rearing_min_z = QLineEdit(); form.addRow("rearing 最低 Z", self.rearing_min_z)
        self.run_analysis_button = QPushButton("分析并导出事件明细"); self.run_analysis_button.clicked.connect(self._run_analysis); form.addRow(self.run_analysis_button)
        layout.addLayout(form)
        self.analysis_status = self._notice("请先完成坐标重建。", "#6b7280"); layout.addWidget(self.analysis_status)
        self.summary_text = QPlainTextEdit(); self.summary_text.setReadOnly(True); self.summary_text.setPlaceholderText("分析摘要会显示在这里。"); layout.addWidget(self.summary_text)
        self.events_table = QTableWidget(); self.events_table.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.events_table, 1)
        self._load_preset_into_ui()
        return page

    def _results_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(self._notice("此页的所有导出均写入“重建坐标系”页中你亲自选择的独立结果目录。软件不会自行写到桌面，也不会覆盖同名文件。", "#1e40af"))
        self.results_status = self._notice("请先完成 Cylinder 分析。", "#6b7280"); layout.addWidget(self.results_status)
        self.results_summary = QPlainTextEdit(); self.results_summary.setReadOnly(True); layout.addWidget(self.results_summary)
        button = QPushButton("导出完整报告包（Excel、HTML、PDF、PNG 图）"); button.clicked.connect(self._export_reports); layout.addWidget(button)
        publication_button = QPushButton("导出投稿级图（PNG、PDF、SVG）和三维关键点视频（MP4）")
        publication_button.clicked.connect(self._export_publication_visuals); layout.addWidget(publication_button)
        plots = QHBoxLayout(); self.count_plot = QLabel("事件统计图将在导出后显示"); self.timeline_plot = QLabel("时间轴图将在导出后显示")
        self.count_plot.setAlignment(Qt.AlignCenter); self.timeline_plot.setAlignment(Qt.AlignCenter); plots.addWidget(self.count_plot); plots.addWidget(self.timeline_plot); layout.addLayout(plots, 1)
        return page

    def _load_preset_into_ui(self):
        cfg = load_literature_common_preset()
        self.left_paw.setText(cfg.left_paw_point); self.right_paw.setText(cfg.right_paw_point); self.analysis_radius.setText(str(cfg.cylinder_radius)); self.wall_tolerance.setText(str(cfg.wall_tolerance)); self.contact_min_z.setText(str(cfg.contact_min_z)); self.contact_max_z.setText(str(cfg.contact_max_z)); self.min_contact_frames.setText(str(cfg.min_contact_frames)); self.bilateral_window.setText(str(cfg.bilateral_window_frames)); self.minimum_likelihood.setText("" if cfg.minimum_likelihood is None else str(cfg.minimum_likelihood)); self.only_rearing.setChecked(cfg.only_during_rearing); self.rearing_point.setText(cfg.rearing_point or ""); self.rearing_min_z.setText("" if cfg.rearing_min_z is None else str(cfg.rearing_min_z))

    def _analysis_config(self) -> CylinderConfig:
        base = load_literature_common_preset()
        return CylinderConfig.from_mapping({
            **base.__dict__,
            "preset_name": "文献常用预设" if self.analysis_preset.currentIndex() == 0 else "用户自定义规则",
            "left_paw_point": self.left_paw.text().strip(), "right_paw_point": self.right_paw.text().strip(),
            "cylinder_radius": float(self.analysis_radius.text()), "wall_tolerance": float(self.wall_tolerance.text()),
            "contact_min_z": float(self.contact_min_z.text()), "contact_max_z": float(self.contact_max_z.text()),
            "min_contact_frames": int(self.min_contact_frames.text()), "bilateral_window_frames": int(self.bilateral_window.text()),
            "minimum_likelihood": float(self.minimum_likelihood.text()) if self.minimum_likelihood.text().strip() else None,
            "only_during_rearing": self.only_rearing.isChecked(), "rearing_point": self.rearing_point.text().strip() or None,
            "rearing_min_z": float(self.rearing_min_z.text()) if self.rearing_min_z.text().strip() else None,
        })

    def _run_analysis(self):
        if self.transformed is None:
            QMessageBox.warning(self, "尚无重建数据", "请先完成坐标系重建；本阶段不会用原始坐标进行 cylinder 分析。"); return
        if not self.output_dir.text().strip():
            QMessageBox.warning(self, "需要结果目录", "请先选择独立结果目录。"); return
        try:
            self.analysis_result = analyze_cylinder(self.transformed, self._analysis_config())
            paths = write_cylinder_outputs(self._result_folder("analysis"), self.analysis_result, concise_names=True)
            summary = self.analysis_result.summary
            self.summary_text.setPlainText("\n".join([f"{key}: {value}" for key, value in summary.items() if key not in {"config", "created_at_utc"}]) + f"\n\n事件明细：{paths['events']}\n候选与排除审计：{paths['event_audit']}\n每帧质量：{paths['frame_quality']}")
            self._show_events(self.analysis_result.events)
            self._refresh_results_page()
            self.analysis_status.setText("Cylinder 分析完成。请查看逐事件表和导出的审计文件，再由实验人员判断规则是否合理。"); self.analysis_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
        except (ValueError, DataContractError, FileExistsError, OSError) as error:
            self.analysis_status.setText("未生成事件结果：" + str(error)); self.analysis_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")

    def _show_events(self, events: pd.DataFrame):
        display = events.head(100); self.events_table.setRowCount(len(display)); self.events_table.setColumnCount(len(display.columns)); self.events_table.setHorizontalHeaderLabels(list(display.columns))
        for row_index, (_, row) in enumerate(display.iterrows()):
            for col_index, value in enumerate(row): self.events_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        self.events_table.resizeColumnsToContents()

    def _refresh_results_page(self):
        if self.analysis_result is None: return
        summary = self.analysis_result.summary
        keys = ["left_touch_events", "right_touch_events", "bilateral_touch_events", "total_effective_events", "left_usage_proportion", "right_usage_proportion", "laterality_index", "laterality_formula"]
        self.results_summary.setPlainText("\n".join(f"{key}: {summary.get(key)}" for key in keys))
        self.results_status.setText("分析结果已就绪。确认逐事件表与参数后可导出完整报告包。")
        self.results_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")

    def _export_reports(self):
        if self.analysis_result is None:
            QMessageBox.warning(self, "尚无分析结果", "请先完成 Cylinder 分析。"); return
        try:
            paths = write_report_bundle(self._result_folder("reports"), self.analysis_result, concise_names=True)
            for label, key in ((self.count_plot, "counts_plot"), (self.timeline_plot, "timeline_plot")):
                pixmap = QPixmap(str(paths[key])); label.setPixmap(pixmap.scaled(480, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.results_status.setText(f"报告导出完成：Excel {paths['excel']}；HTML {paths['html']}；PDF {paths['pdf']}")
        except (FileExistsError, OSError, RuntimeError) as error:
            self.results_status.setText("未导出报告：" + str(error)); self.results_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")

    def _export_publication_visuals(self):
        if self.analysis_result is None or self.transformed is None:
            QMessageBox.warning(self, "尚无分析结果", "请先完成坐标重建和 Cylinder 分析。"); return
        output_text = self.output_dir.text().strip()
        if not output_text:
            QMessageBox.warning(self, "需要结果目录", "请先在“重建坐标系”页选择独立结果目录。"); return
        try:
            figure_paths = write_publication_figure(self._result_folder("figures"), self.transformed, self.analysis_result)
            video_path = write_3d_keypoint_video(self._result_folder("video"), self.transformed, self.analysis_result)
            pixmap = QPixmap(str(figure_paths["png"])); self.count_plot.setPixmap(pixmap.scaled(480, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.results_status.setText(f"投稿级图与三维 MP4 已导出到你选择的目录：PNG {figure_paths['png']}；PDF {figure_paths['pdf']}；SVG {figure_paths['svg']}；MP4 {video_path}")
            self.results_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
        except (FileExistsError, OSError, RuntimeError, ValueError) as error:
            self.results_status.setText("未导出投稿级可视化：" + str(error)); self.results_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")

    def _select_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择原始 CSV", str(Path.home()), "CSV 文件 (*.csv)")
        if not path: return
        self.csv_path.setText(path)
        try:
            self.df = pd.read_csv(path); self.input_path = Path(path)
            result = validate_wide_csv(self.df)
            self.import_status.setText(f"导入成功：{len(self.df)} 帧，单位 {result['coordinate_unit']}，fps {result['fps']}。")
            self.import_status.setStyleSheet("padding: 10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
            self.points_label.setText("识别到的完整 XYZ 点：" + "、".join(result['point_names']))
            self._show_preview(); self.raw_preview.set_data(self.df); self._suggest_output()
        except (OSError, pd.errors.ParserError, DataContractError) as error:
            self.df = None; self.import_status.setText("导入未通过：" + str(error)); self.import_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")

    def _select_metadata(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 metadata", str(Path.home()), "JSON 文件 (*.json)")
        if not path: return
        try:
            self.metadata = json.loads(Path(path).read_text(encoding="utf-8")); self.metadata_path.setText(path)
            reference = self.metadata.get("coordinate_reference", {})
            cylinder = self.metadata.get("cylinder", {})
            if "radius" in cylinder:
                self.radius.setText(str(cylinder['radius']))
                self.analysis_radius.setText(str(cylinder['radius']))
            mapping = self.metadata.get("body_point_mapping", {})
            if "left_forepaw_tip" in mapping: self.left_paw.setText(str(mapping["left_forepaw_tip"]))
            if "right_forepaw_tip" in mapping: self.right_paw.setText(str(mapping["right_forepaw_tip"]))
            self.reconstruction_status.setText("metadata 已载入。请确认其中固定参考的物理含义后再生成结果。")
        except (OSError, json.JSONDecodeError) as error:
            QMessageBox.warning(self, "metadata 无法读取", str(error))

    def _show_preview(self):
        assert self.df is not None
        preview = self.df.head(20); self.preview_table.setRowCount(len(preview)); self.preview_table.setColumnCount(len(preview.columns)); self.preview_table.setHorizontalHeaderLabels(list(preview.columns))
        for row_index, (_, row) in enumerate(preview.iterrows()):
            for col_index, value in enumerate(row): self.preview_table.setItem(row_index, col_index, QTableWidgetItem(str(value)))
        self.preview_table.resizeColumnsToContents()

    def _suggest_output(self):
        if self.input_path and not self.output_dir.text(): self.output_dir.setText(str(self.input_path.parent / "behavior3d_results"))

    def _result_folder(self, category: str) -> Path:
        """所有导出都从用户在 GUI 中选择的根目录派生，分类保存且不猜测桌面路径。"""
        return Path(self.output_dir.text().strip()) / category

    def _select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择独立结果目录", self.output_dir.text() or str(Path.home()))
        if path: self.output_dir.setText(path)

    def _run_reconstruction(self):
        if self.df is None or self.input_path is None:
            QMessageBox.warning(self, "尚未导入", "请先载入并通过验证的 CSV。"); return
        if not self.output_dir.text().strip():
            QMessageBox.warning(self, "需要结果目录", "请选择与原始 CSV 分开的结果目录。"); return
        try:
            choice = self.method.currentIndex()
            if choice == 0:
                reference = self.metadata.get("coordinate_reference")
                if not reference: raise ReconstructionError("metadata 中没有 coordinate_reference；请选择固定环境标记或多点拟合。")
                self.transformed, self.transform_record = reconstruction_from_metadata(self.df, reference)
            elif choice == 1:
                self.transformed, self.transform_record = reconstruction_from_environment_markers(self.df, bottom_center_marker=self.bottom_marker.text().strip(), top_center_marker=self.top_marker.text().strip(), x_axis_marker=self.x_marker.text().strip(), max_marker_drift=float(self.max_drift.text()))
            else:
                names = [name.strip() for name in self.perimeter.text().split(",") if name.strip()]
                vertical = json.loads(self.vertical_hint.text())
                self.transformed, self.transform_record = reconstruction_from_perimeter_points(self.df, perimeter_markers=names, x_axis_marker=self.x_marker.text().strip(), vertical_reference_raw=vertical, expected_radius=float(self.radius.text()), max_plane_residual=float(self.plane_residual.text()), max_circle_residual=float(self.circle_residual.text()))
            data_folder = self._result_folder("data")
            output = data_folder / "coordinates.csv"
            csv_path, record_path = write_reconstruction_outputs(self.input_path, output, self.transformed, self.transform_record, record_path=data_folder / "transform.json")
            self.new_preview.set_data(self.transformed, reconstructed=True)
            self.reconstruction_status.setText(f"重建成功。新坐标：{csv_path}；审计记录：{record_path}")
            self.reconstruction_status.setStyleSheet("padding:10px; background:#ecfdf5; color:#065f46; border-radius:4px;")
        except (ValueError, DataContractError, ReconstructionError, FileExistsError, OSError, json.JSONDecodeError) as error:
            self.reconstruction_status.setText("未生成结果：" + str(error)); self.reconstruction_status.setStyleSheet("padding:10px; background:#fef2f2; color:#991b1b; border-radius:4px;")
