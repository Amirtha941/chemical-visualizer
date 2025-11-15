import sys
import requests
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt


class ChemicalVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Equipment Parameter Visualizer")
        self.setGeometry(200, 200, 900, 700)

        self.layout = QVBoxLayout()
        self.label = QLabel("Upload a CSV to analyze chemical equipment data")
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)

        self.upload_btn = QPushButton("Upload CSV")
        self.upload_btn.clicked.connect(self.upload_csv)
        self.layout.addWidget(self.upload_btn)

        self.chart_canvas = None
        self.setLayout(self.layout)

    def upload_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            url = "http://127.0.0.1:8000/api/upload/"
            files = {'file': open(file_path, 'rb')}
            response = requests.post(url, files=files)

            if response.status_code == 201:
                summary = response.json()['summary']
                self.show_summary(summary)
            else:
                QMessageBox.warning(self, "Upload Failed", f"Server error: {response.text}")

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def show_summary(self, summary):
        averages = summary['averages']
        type_distribution = summary.get('type_distribution', {})

        # Remove old chart if exists
        if self.chart_canvas:
            self.layout.removeWidget(self.chart_canvas)
            self.chart_canvas.setParent(None)

        # Create figure with 2 subplots: bar + pie
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        # --- Bar Chart ---
        axes[0].bar(averages.keys(), averages.values(), color='skyblue')
        axes[0].set_title("Parameter Averages")
        axes[0].set_ylabel("Value")
        axes[0].set_xlabel("Parameter")
        axes[0].grid(True, axis='y', linestyle='--', alpha=0.7)

        # --- Pie Chart ---
        if type_distribution:
            labels = list(type_distribution.keys())
            values = list(type_distribution.values())
            axes[1].pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
            axes[1].set_title("Equipment Type Distribution")
        else:
            axes[1].text(0.5, 0.5, "No 'Type' column found", ha='center', va='center')

        plt.tight_layout()
        self.chart_canvas = FigureCanvas(fig)
        self.layout.addWidget(self.chart_canvas)
        self.chart_canvas.draw()

        QMessageBox.information(self, "Success", "Data uploaded and charts updated successfully!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChemicalVisualizer()
    window.show()
    sys.exit(app.exec_())
