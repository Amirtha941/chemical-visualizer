"""
main_desktop.py
PyQt5 desktop client for Chemical Equipment Parameter Visualizer.

Features:
- Choose CSV file and upload to Django backend (/api/upload/)
- Fetch last datasets from /api/datasets/
- Display quick summary (total, most common type, highest/lowest averages)
- Show bar chart (averages) and pie chart (type distribution) using Matplotlib
- Simple history list to load older summaries

Dependencies:
pip install PyQt5 matplotlib requests
(also: your backend environment should be running)

Usage:
python main_desktop.py
"""

import sys
import os
import requests
import json
from datetime import datetime
from io import BytesIO

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QLabel, QListWidget, QGroupBox, QGridLayout, QMessageBox,
    QTableWidget, QTableWidgetItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# --- Config (change backend URL if needed) ---
BACKEND_BASE = "http://127.0.0.1:8000"
UPLOAD_ENDPOINT = f"{BACKEND_BASE}/api/upload/"
LIST_ENDPOINT = f"{BACKEND_BASE}/api/datasets/"

# ---------- Helper chart canvas ----------
class MplCanvas(FigureCanvas):
    def __init__(self, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        super().__init__(fig)
        self.axes = fig.add_subplot(111)

# ---------- Main App Window ----------
class DesktopApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Equipment Parameter Visualizer — Desktop")
        self.resize(1100, 720)
        self.selected_file = None
        self.datasets = []  # fetched list of summaries

        self._init_ui()
        self.fetch_datasets()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        top_row = QHBoxLayout()

        # Upload controls
        upload_box = QGroupBox("Upload CSV")
        upload_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setMinimumWidth(400)
        choose_btn = QPushButton("Choose CSV")
        choose_btn.clicked.connect(self.choose_file)
        upload_btn = QPushButton("Upload")
        upload_btn.clicked.connect(self.upload_file)
        upload_layout.addWidget(self.file_label)
        upload_layout.addWidget(choose_btn)
        upload_layout.addWidget(upload_btn)
        upload_box.setLayout(upload_layout)

        # Summary card
        summary_box = QGroupBox("Quick Summary")
        summary_layout = QGridLayout()
        self.lbl_total = QLabel("Total records: —")
        self.lbl_most = QLabel("Most common type: —")
        self.lbl_high = QLabel("Highest avg: —")
        self.lbl_low = QLabel("Lowest avg: —")
        # styling
        for lbl in [self.lbl_total, self.lbl_most, self.lbl_high, self.lbl_low]:
            lbl.setStyleSheet("font-size:14px;")
        summary_layout.addWidget(self.lbl_total, 0, 0)
        summary_layout.addWidget(self.lbl_most, 1, 0)
        summary_layout.addWidget(self.lbl_high, 2, 0)
        summary_layout.addWidget(self.lbl_low, 3, 0)
        summary_box.setLayout(summary_layout)
        summary_box.setMaximumWidth(380)

        # History list
        history_box = QGroupBox("Last uploads")
        history_layout = QVBoxLayout()
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_clicked)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.fetch_datasets)
        history_layout.addWidget(self.history_list)
        history_layout.addWidget(refresh_btn)
        history_box.setLayout(history_layout)
        history_box.setMaximumWidth(380)

        top_row.addWidget(upload_box, stretch=2)
        top_row.addWidget(summary_box, stretch=1)
        top_row.addWidget(history_box, stretch=1)

        # Charts and table
        middle_row = QHBoxLayout()
        # Bar chart canvas (averages)
        self.bar_canvas = MplCanvas(width=5, height=4, dpi=100)
        # Pie chart canvas (types)
        self.pie_canvas = MplCanvas(width=5, height=4, dpi=100)

        chart_group = QGroupBox("Charts")
        chart_layout = QHBoxLayout()
        chart_layout.addWidget(self.bar_canvas)
        chart_layout.addWidget(self.pie_canvas)
        chart_group.setLayout(chart_layout)

        # Table of averages (or data)
        table_group = QGroupBox("Averages Table")
        table_layout = QVBoxLayout()
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Parameter", "Average"])
        self.table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        table_group.setMaximumWidth(360)

        middle_row.addWidget(chart_group, stretch=3)
        middle_row.addWidget(table_group, stretch=1)

        # Footer info / status
        bottom_row = QHBoxLayout()
        self.status_label = QLabel("")
        bottom_row.addWidget(self.status_label, alignment=Qt.AlignLeft)
        # PDF/report & exit buttons (basic)
        pdf_btn = QPushButton("Download PDF (server)")  # requires backend endpoint if implemented
        pdf_btn.clicked.connect(self.download_pdf)
        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.close)
        bottom_row.addWidget(pdf_btn, alignment=Qt.AlignRight)
        bottom_row.addWidget(exit_btn, alignment=Qt.AlignRight)

        main_layout.addLayout(top_row)
        main_layout.addSpacing(10)
        main_layout.addLayout(middle_row)
        main_layout.addStretch()
        main_layout.addLayout(bottom_row)

        self.setLayout(main_layout)

    # ---------- UI actions ----------
    def choose_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Choose CSV file", os.getcwd(), "CSV files (*.csv)")
        if fname:
            self.selected_file = fname
            display = os.path.basename(fname)
            self.file_label.setText(display)

    def upload_file(self):
        if not self.selected_file:
            QMessageBox.warning(self, "No file", "Please choose a CSV file first.")
            return

        try:
            with open(self.selected_file, "rb") as f:
                files = {"file": (os.path.basename(self.selected_file), f, "text/csv")}
                self.status_label.setText("Uploading...")
                QApplication.processEvents()
                res = requests.post(UPLOAD_ENDPOINT, files=files, timeout=20)
        except Exception as e:
            QMessageBox.critical(self, "Upload error", f"Failed to upload: {e}")
            self.status_label.setText("")
            return

        if res.status_code in (200, 201):
            self.status_label.setText("Upload succeeded.")
            try:
                data = res.json()
                summary = data.get("summary")
                if summary:
                    self.populate_summary(summary)
            except Exception:
                pass
            self.fetch_datasets()
        else:
            msg = f"Upload failed: {res.status_code}\n{res.text}"
            QMessageBox.critical(self, "Upload failed", msg)
            self.status_label.setText("Upload failed.")

    def fetch_datasets(self):
        try:
            self.status_label.setText("Fetching history...")
            QApplication.processEvents()
            res = requests.get(LIST_ENDPOINT, timeout=10)
            if res.status_code == 200:
                self.datasets = res.json()
                self._populate_history_list()
                # automatically load latest summary if present
                if self.datasets:
                    self.populate_summary(self.datasets[0].get("summary", {}))
                self.status_label.setText("Ready.")
            else:
                self.status_label.setText(f"Error fetching datasets: {res.status_code}")
        except Exception as e:
            self.status_label.setText("Error fetching datasets.")
            QMessageBox.critical(self, "Network error", f"Failed to fetch datasets: {e}")

    def _populate_history_list(self):
        self.history_list.clear()
        for ds in self.datasets:
            fname = ds.get("filename", "unknown.csv")
            uploaded = ds.get("uploaded_at")
            try:
                when = datetime.fromisoformat(uploaded.replace("Z", "+00:00")).strftime("%d/%m/%Y %I:%M:%S %p")
            except Exception:
                when = uploaded or ""
            self.history_list.addItem(f"{fname}  ({when})")

    def on_history_clicked(self, item):
        idx = self.history_list.currentRow()
        if idx < 0 or idx >= len(self.datasets):
            return
        summary = self.datasets[idx].get("summary", {})
        self.populate_summary(summary)

    # ---------- Populate UI from summary ----------
    def populate_summary(self, summary):
        """
        summary expected format:
        {
          "total_count": int,
          "averages": {"Flowrate": 119.8, ...},
          "type_distribution": {"Pump": 4, ...}
        }
        """
        if not summary:
            QMessageBox.information(self, "No data", "Summary is empty.")
            return

        total = summary.get("total_count", 0)
        averages = summary.get("averages", {}) or {}
        types = summary.get("type_distribution", {}) or {}

        # quick textual summary
        self.lbl_total.setText(f"Total records: {total}")
        if types:
            top = sorted(types.items(), key=lambda x: x[1], reverse=True)[0]
            self.lbl_most.setText(f"Most common type: {top[0]} ({top[1]})")
        else:
            self.lbl_most.setText("Most common type: —")

        # highest and lowest average
        if averages:
            items = list(averages.items())
            highest = max(items, key=lambda x: x[1])
            lowest = min(items, key=lambda x: x[1])
            self.lbl_high.setText(f"Highest avg: {highest[0]} — {highest[1]:.2f}")
            self.lbl_low.setText(f"Lowest avg: {lowest[0]} — {lowest[1]:.2f}")
        else:
            self.lbl_high.setText("Highest avg: —")
            self.lbl_low.setText("Lowest avg: —")

        # fill table
        self.table.setRowCount(0)
        for k, v in averages.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(k)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{v:.4g}" if isinstance(v, (int, float)) else str(v)))

        # plot charts
        self._plot_bar(averages)
        self._plot_pie(types)

    def _plot_bar(self, averages):
        self.bar_canvas.axes.clear()
        if not averages:
            self.bar_canvas.axes.text(0.5, 0.5, "No numeric averages", ha="center", va="center")
            self.bar_canvas.draw()
            return
        labels = list(averages.keys())
        values = [float(v) for v in averages.values()]
        bars = self.bar_canvas.axes.bar(labels, values, color="#2aa6d6", alpha=0.8)
        self.bar_canvas.axes.set_ylabel("Average")
        self.bar_canvas.axes.set_title("Parameter Averages")
        self.bar_canvas.axes.grid(axis="y", linestyle="--", alpha=0.3)
        # rotate labels if many
        if len(labels) > 4:
            self.bar_canvas.axes.set_xticklabels(labels, rotation=30, ha="right")
        self.bar_canvas.draw()

    def _plot_pie(self, types):
        self.pie_canvas.axes.clear()
        if not types:
            self.pie_canvas.axes.text(0.5, 0.5, "No type distribution", ha="center", va="center")
            self.pie_canvas.draw()
            return
        labels = list(types.keys())
        sizes = [int(v) for v in types.values()]
        # choose colors (repeatable)
        colors = ["#00b4d8", "#48cae4", "#90e0ef", "#ffafcc", "#cdb4db", "#bde0fe", "#ffc857"]
        colors = colors[:len(labels)]
        wedges, texts, autotexts = self.pie_canvas.axes.pie(
            sizes, labels=labels, autopct="%1.1f%%", startangle=90, colors=colors, textprops={"color": "w"}
        )
        self.pie_canvas.axes.set_title("Equipment Type Distribution")
        # legend on the side
        # self.pie_canvas.axes.legend(wedges, labels, title="Types", loc="center left", bbox_to_anchor=(1, 0.5))
        self.pie_canvas.draw()

    # ---------- Optional: download report from backend (if implemented) ----------
    def download_pdf(self):
        # Backend must implement an endpoint to return PDF for a dataset id, e.g. /api/report/{id}/
        # Here we just attempt to download a "report" for the latest dataset if backend supports it.
        if not self.datasets:
            QMessageBox.information(self, "No datasets", "No dataset available to generate report.")
            return
        ds_id = self.datasets[0].get("id")
        if not ds_id:
            QMessageBox.information(self, "No id", "Latest dataset has no id.")
            return
        url = f"{BACKEND_BASE}/api/report/{ds_id}/"  # make sure backend has this route
        try:
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                fname, _ = QFileDialog.getSaveFileName(self, "Save Report", f"report_{ds_id}.pdf", "PDF files (*.pdf)")
                if fname:
                    with open(fname, "wb") as f:
                        f.write(res.content)
                    QMessageBox.information(self, "Saved", f"Report saved to {fname}")
            else:
                QMessageBox.warning(self, "Report error", f"Report not available (status {res.status_code})")
        except Exception as e:
            QMessageBox.critical(self, "Network error", f"Failed to download report: {e}")

# ---------- run ----------
def main():
    app = QApplication(sys.argv)
    window = DesktopApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
