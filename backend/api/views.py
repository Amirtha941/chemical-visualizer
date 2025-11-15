from rest_framework.views import APIView
from rest_framework.decorators import api_view,permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import authenticate
from django.http import HttpResponse
from .serializers import FileUploadSerializer
from .models import Dataset
import pandas as pd
from io import BytesIO   # ✅ Add this line
import re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import matplotlib
matplotlib.use("Agg")   # Prevents GUI errors in backend


class UploadCSVView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = FileUploadSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file = serializer.validated_data["file"]
        dataset = Dataset.objects.create(file=file, filename=file.name)

        try:
            df = pd.read_csv(dataset.file.path)
        except Exception as e:
            dataset.delete()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if df.empty:
            dataset.delete()
            return Response({"error": "Uploaded CSV is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # 🧪 Debug logs
        print("\n========== CSV DIAGNOSTICS ==========")
        print("Raw columns:", list(df.columns))
        print("Data types before cleaning:\n", df.dtypes.head())
        print("First few rows:\n", df.head(3))

        # Clean column names (remove units, symbols, spaces)
        df.columns = [re.sub(r"[^a-zA-Z0-9]", "", str(c)).strip().capitalize() for c in df.columns]
        print("Cleaned columns:", list(df.columns))

        total_count = len(df)

        # Detect “Type” or similar column
        type_col = next((col for col in df.columns if "type" in col.lower()), None)
        type_dist = df[type_col].value_counts().to_dict() if type_col else {}

        # Try converting all numeric-like columns
        numeric_df = df.copy()
        for col in numeric_df.columns:
            numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")

        numeric_df = numeric_df.dropna(axis=1, how="all").select_dtypes(include="number")

        print("Numeric columns after conversion:", list(numeric_df.columns))
        print("Averages computed:\n", numeric_df.mean())

        averages = numeric_df.mean().round(3).to_dict()

        summary = {
            "total_count": total_count,
            "averages": averages,
            "type_distribution": type_dist,
        }

        dataset.summary = summary
        dataset.save()

        return Response({
            "id": dataset.id,
            "filename": dataset.filename,
            "uploaded_at": dataset.uploaded_at,
            "summary": summary,
        }, status=status.HTTP_201_CREATED)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_datasets(request):
    """Return last 5 uploaded datasets with summaries."""
    datasets = Dataset.objects.order_by("-uploaded_at")[:5]

    data = []
    for ds in datasets:
        data.append(
            {
                "id": ds.id,
                "filename": ds.filename,
                "uploaded_at": ds.uploaded_at,
                "summary": ds.summary,
            }
        )

    return Response(data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_report(request, pk):
    """
    Generate a PDF summary (with charts) for a given dataset ID.
    """
    from matplotlib import pyplot as plt

    try:
        dataset = Dataset.objects.get(id=pk)
    except Dataset.DoesNotExist:
        return Response({"error": "Dataset not found"}, status=status.HTTP_404_NOT_FOUND)

    summary = dataset.summary or {}
    averages = summary.get("averages", {})
    type_dist = summary.get("type_distribution", {})
    total_count = summary.get("total_count", 0)

    # Create a new PDF buffer
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # ===== HEADER =====
    p.setFont("Helvetica-Bold", 18)
    p.drawString(1 * inch, height - 1 * inch, "Chemical Equipment Summary Report")
    p.setFont("Helvetica", 11)
    p.setFillColor(colors.darkgray)
    p.drawString(1 * inch, height - 1.3 * inch, f"Dataset: {dataset.filename}")
    p.drawString(1 * inch, height - 1.5 * inch, f"Uploaded: {dataset.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}")
    p.setFillColor(colors.black)

    # ===== QUICK SUMMARY =====
    p.setFont("Helvetica-Bold", 13)
    p.drawString(1 * inch, height - 2 * inch, "Quick Summary:")
    p.setFont("Helvetica", 11)
    y = height - 2.3 * inch
    p.drawString(1.2 * inch, y, f"Total Records: {total_count}")
    y -= 0.25 * inch

    if type_dist:
        top_type = max(type_dist.items(), key=lambda x: x[1])
        p.drawString(1.2 * inch, y, f"Most Common Type: {top_type[0]} ({top_type[1]} occurrences)")
        y -= 0.3 * inch


    # ===== CHART 1: AVERAGE BAR CHART =====
    if averages:
        fig, ax = plt.subplots(figsize=(4, 2.5))
        ax.bar(averages.keys(), averages.values(), color="#00b4d8")
        ax.set_title("Parameter Averages", fontsize=10)
        plt.tight_layout()

        img_buf = BytesIO()
        plt.savefig(img_buf, format='PNG', dpi=120)
        plt.close(fig)
        img_buf.seek(0)

        p.drawImage(
            ImageReader(img_buf),
            1 * inch, height - 5.5 * inch,
            width=3.5 * inch, height=2.3 * inch
    )



    # ===== CHART 2: TYPE DISTRIBUTION PIE CHART =====
    if type_dist:
        fig, ax = plt.subplots(figsize=(3, 2.5))
        ax.pie(type_dist.values(), labels=type_dist.keys(), autopct="%1.1f%%", startangle=90)
        ax.set_title("Equipment Type Distribution", fontsize=10)
        plt.tight_layout()

        img_buf2 = BytesIO()
        plt.savefig(img_buf2, format='PNG', dpi=120)
        plt.close(fig)
        img_buf2.seek(0)

        p.drawImage(
            ImageReader(img_buf2),
            4.8 * inch, height - 5.5 * inch,
            width=3 * inch, height=2.3 * inch
        )

    # ===== FOOTER =====
    p.setFont("Helvetica-Oblique", 10)
    p.setFillColor(colors.gray)
    p.drawString(1 * inch, 0.7 * inch, "Generated by Chemical Equipment Visualizer © 2025")
    p.showPage()
    p.save()

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="report_{dataset.id}.pdf"'
    response.write(pdf)
    return response
