"""
DocumentFactory - factory for creating test PDF documents.

Wraps the existing DocumentGenerator from the standalone stress test script
and exposes a clean factory interface consistent with the multi-agent
NodeFactory / TaskFactory patterns.

Supports two content profiles:
- **simple** — text-only paragraphs (default, lightweight).
- **complex** — text interleaved with data tables, procedurally-generated
  PNG images, and bar/pie/line charts for realistic RAG workloads.
"""

import random
import string
import struct
import time
import zlib
from io import BytesIO
from datetime import datetime
from typing import List, Optional, Tuple, Union


class DocumentFactory:
    """
    Factory for generating test PDF documents.

    Provides static methods for creating individual and batches of PDF
    documents used in RAG upload and embedding stress tests.
    """

    TOPICS = [
        "Artificial Intelligence", "Machine Learning", "Deep Learning",
        "Cloud Computing", "Blockchain Technology", "Quantum Computing",
        "Cybersecurity", "Internet of Things", "Big Data Analytics",
        "Natural Language Processing", "Computer Vision", "Robotics",
        "Edge Computing", "5G Networks", "Augmented Reality",
        "Virtual Reality", "DevOps", "Microservices", "Kubernetes",
        "Docker Containers", "Serverless Computing", "API Design",
        "Database Management", "Data Warehousing", "ETL Processes",
    ]

    PALETTE: Optional[list] = None  # lazily populated on first complex PDF

    @classmethod
    def _get_palette(cls) -> list:
        """Return ReportLab HexColor palette, importing lazily."""
        if cls.PALETTE is None:
            from reportlab.lib.colors import HexColor
            cls.PALETTE = [
                HexColor("#4A90D9"), HexColor("#50C878"),
                HexColor("#FF6B6B"), HexColor("#F7DC6F"),
                HexColor("#BB8FCE"), HexColor("#48C9B0"),
                HexColor("#F0B27A"), HexColor("#85C1E9"),
            ]
        return cls.PALETTE

    # ------------------------------------------------------------------
    # Text content generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_content(doc_id: int, topic: str = None) -> str:
        """Generate unique textual content for a document.

        Args:
            doc_id: Numeric identifier used to seed unique values.
            topic: Optional topic override; random if not provided.

        Returns:
            Multi-paragraph string with unique content.
        """
        if topic is None:
            topic = random.choice(DocumentFactory.TOPICS)

        unique_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=16)
        )

        content = (
            f"Document ID: {doc_id}\n"
            f"Unique Identifier: {unique_id}\n"
            f"Topic: {topic}\n"
            f"Generated: {datetime.now().isoformat()}\n\n"
            f"Introduction to {topic}\n"
            f"{'=' * 50}\n\n"
            f"This document discusses the fundamentals and advanced concepts of {topic}.\n"
            f"Each document in this stress test contains unique content to ensure proper\n"
            f"handling of distinct documents by the system.\n\n"
            f"Section 1: Overview\n"
            f"{'-' * 30}\n"
            f"{topic} represents a significant advancement in modern technology.\n"
            f"Random data: {random.random()}\n"
            f"Timestamp: {time.time()}\n\n"
        )

        for i in range(5):
            content += (
                f"Section {i + 2}: Detailed Analysis Part {i + 1}\n"
                f"{'-' * 30}\n"
                f"This section contains unique information about {topic} with random data:\n"
                f"{''.join(random.choices(string.ascii_letters, k=200))}\n\n"
                f"Key Points:\n"
                f"- Point 1: Random value {random.randint(1000, 9999)}\n"
                f"- Point 2: Unique timestamp {time.time()}\n"
                f"- Point 3: Random string {unique_id[:8]}\n\n"
            )

        return content

    # ------------------------------------------------------------------
    # Procedural PNG generation (no external image files)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_png_bytes(width: int, height: int, seed: int) -> bytes:
        """Generate a minimal valid PNG with a random gradient pattern."""
        rng = random.Random(seed)
        r0, g0, b0 = rng.randint(30, 200), rng.randint(30, 200), rng.randint(30, 200)
        r1, g1, b1 = rng.randint(30, 200), rng.randint(30, 200), rng.randint(30, 200)

        raw_rows = []
        for y in range(height):
            t = y / max(height - 1, 1)
            row = b"\x00"
            for x in range(width):
                s = x / max(width - 1, 1)
                r = int(r0 + (r1 - r0) * s * t) & 0xFF
                g = int(g0 + (g1 - g0) * (1 - s) * t) & 0xFF
                b = int(b0 + (b1 - b0) * s * (1 - t)) & 0xFF
                row += struct.pack("BBB", r, g, b)
            raw_rows.append(row)

        raw_data = b"".join(raw_rows)

        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        idat_data = zlib.compress(raw_data)

        png = b"\x89PNG\r\n\x1a\n"
        png += _chunk(b"IHDR", ihdr_data)
        png += _chunk(b"IDAT", idat_data)
        png += _chunk(b"IEND", b"")
        return png

    @staticmethod
    def _make_image_flowable(
        width_in: float, height_in: float, seed: int,
    ):
        """Return a ReportLab Image flowable backed by an in-memory PNG."""
        from reportlab.platypus import Image
        from reportlab.lib.units import inch

        px_w = min(int(width_in * 72), 200)
        px_h = min(int(height_in * 72), 150)
        buf = BytesIO(DocumentFactory._make_png_bytes(px_w, px_h, seed))
        return Image(buf, width=width_in * inch, height=height_in * inch)

    # ------------------------------------------------------------------
    # Chart helpers (vector ReportLab drawings)
    # ------------------------------------------------------------------

    @staticmethod
    def _make_bar_chart(title: str, seed: int):
        """Create a bar chart Drawing."""
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.barcharts import VerticalBarChart

        rng = random.Random(seed)
        d = Drawing(400, 200)
        chart = VerticalBarChart()
        chart.x, chart.y = 50, 30
        chart.width, chart.height = 300, 130
        n_groups = rng.randint(4, 8)
        chart.data = [
            [rng.randint(10, 100) for _ in range(n_groups)],
            [rng.randint(10, 100) for _ in range(n_groups)],
        ]
        chart.categoryAxis.categoryNames = [
            f"Cat-{chr(65 + i)}" for i in range(n_groups)
        ]
        palette = DocumentFactory._get_palette()
        for i in range(2):
            chart.bars[i].fillColor = palette[i % len(palette)]
        d.add(chart)
        d.add(String(200, 185, title, textAnchor="middle", fontSize=10))
        return d

    @staticmethod
    def _make_pie_chart(title: str, seed: int):
        """Create a pie chart Drawing."""
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.piecharts import Pie

        rng = random.Random(seed)
        d = Drawing(300, 200)
        pie = Pie()
        pie.x, pie.y = 75, 20
        pie.width = pie.height = 150
        n_slices = rng.randint(4, 7)
        pie.data = [rng.randint(5, 40) for _ in range(n_slices)]
        pie.labels = [f"Slice {i + 1}" for i in range(n_slices)]
        palette = DocumentFactory._get_palette()
        for i in range(n_slices):
            pie.slices[i].fillColor = palette[i % len(palette)]
        d.add(pie)
        d.add(String(150, 185, title, textAnchor="middle", fontSize=10))
        return d

    @staticmethod
    def _make_line_chart(title: str, seed: int):
        """Create a line chart Drawing."""
        from reportlab.graphics.shapes import Drawing, String
        from reportlab.graphics.charts.lineplots import LinePlot

        rng = random.Random(seed)
        d = Drawing(400, 200)
        lp = LinePlot()
        lp.x, lp.y = 50, 30
        lp.width, lp.height = 300, 130
        n_points = rng.randint(8, 15)
        lp.data = [
            [(i, rng.uniform(10, 90)) for i in range(n_points)],
            [(i, rng.uniform(10, 90)) for i in range(n_points)],
        ]
        palette = DocumentFactory._get_palette()
        for i in range(2):
            lp.lines[i].strokeColor = palette[i % len(palette)]
            lp.lines[i].strokeWidth = 2
        d.add(lp)
        d.add(String(200, 185, title, textAnchor="middle", fontSize=10))
        return d

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_data_table(rows: int, cols: int, seed: int):
        """Create a styled data table."""
        from reportlab.platypus import Table
        from reportlab.lib.colors import HexColor, white, lightgrey
        from reportlab.lib.units import inch
        from reportlab.platypus.tables import TableStyle

        rng = random.Random(seed)
        headers = [f"Column {chr(65 + c)}" for c in range(cols)]
        data = [headers]
        for _ in range(rows):
            data.append([
                f"{rng.uniform(0, 1000):.2f}" if c % 2 == 0
                else rng.choice(["Active", "Pending", "Complete", "Error", "N/A"])
                for c in range(cols)
            ])
        col_width = min(5.5 * inch / cols, 1.5 * inch)
        t = Table(data, colWidths=[col_width] * cols)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#4A90D9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#F2F4F8")]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        return t

    @staticmethod
    def _make_kv_table(pairs: int, seed: int):
        """Create a two-column key/value metrics table."""
        from reportlab.platypus import Table
        from reportlab.lib.colors import HexColor, white, lightgrey
        from reportlab.lib.units import inch
        from reportlab.platypus.tables import TableStyle

        rng = random.Random(seed)
        labels = [
            "Throughput (req/s)", "Latency p50 (ms)", "Latency p99 (ms)",
            "Error rate (%)", "CPU usage (%)", "Memory (MiB)",
            "Queue depth", "Cache hit ratio", "Disk IOPS", "Network (Mbps)",
            "Connections", "Threads", "GC pauses (ms)", "Uptime (h)",
        ]
        rng.shuffle(labels)
        data = [["Metric", "Value"]]
        for i in range(min(pairs, len(labels))):
            data.append([labels[i], f"{rng.uniform(0.1, 999.9):.2f}"])
        t = Table(data, colWidths=[2.5 * inch, 2.0 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#EAECEE")]),
        ]))
        return t

    # ------------------------------------------------------------------
    # Page builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_simple_page(story: list, styles, doc_id: int,
                           page_num: int, topic: str) -> None:
        """Append text-only content for one page."""
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Spacer

        story.append(Paragraph(
            f"Document #{doc_id} &mdash; Page {page_num}: {topic}",
            styles["Heading2"],
        ))
        story.append(Spacer(1, 0.15 * inch))

        unique_id = "".join(
            random.choices(string.ascii_letters + string.digits, k=16)
        )
        story.append(Paragraph(
            f"Generated: {datetime.now().isoformat()} | UID: {unique_id}",
            styles["Normal"],
        ))
        story.append(Spacer(1, 0.1 * inch))

        for section in range(random.randint(3, 6)):
            story.append(Paragraph(
                f"Section {page_num}.{section + 1} &mdash; Analysis",
                styles["Heading3"],
            ))
            body = " ".join(random.choices(string.ascii_letters, k=300))
            story.append(Paragraph(body, styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))

            for b in range(random.randint(2, 5)):
                story.append(Paragraph(
                    f"&bull; Data point {b + 1}: {random.uniform(0, 1000):.4f} "
                    f"(ts={time.time()}, rand={random.randint(1000, 9999)})",
                    styles["Normal"],
                ))
            story.append(Spacer(1, 0.1 * inch))

    @staticmethod
    def _build_complex_page(story: list, styles, doc_id: int,
                            page_num: int, topic: str) -> None:
        """Append rich content: text, tables, images, charts."""
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Spacer

        story.append(Paragraph(
            f"Document #{doc_id} &mdash; Page {page_num}: {topic} (detailed)",
            styles["Heading2"],
        ))
        story.append(Spacer(1, 0.1 * inch))

        body = " ".join(random.choices(string.ascii_letters, k=150))
        story.append(Paragraph(
            f"{body} &mdash; {datetime.now().isoformat()}",
            styles["Normal"],
        ))
        story.append(Spacer(1, 0.1 * inch))

        chart_seed = hash((doc_id, page_num, "chart")) & 0xFFFFFFFF
        chart_choice = page_num % 3
        if chart_choice == 0:
            story.append(DocumentFactory._make_bar_chart(
                f"{topic} - Benchmark Results", chart_seed))
        elif chart_choice == 1:
            story.append(DocumentFactory._make_pie_chart(
                f"{topic} - Distribution", chart_seed))
        else:
            story.append(DocumentFactory._make_line_chart(
                f"{topic} - Trend Analysis", chart_seed))
        story.append(Spacer(1, 0.15 * inch))

        kv_seed = hash((doc_id, page_num, "kv")) & 0xFFFFFFFF
        story.append(DocumentFactory._make_kv_table(
            random.randint(5, 10), kv_seed))
        story.append(Spacer(1, 0.15 * inch))

        img_seed = hash((doc_id, page_num, "img")) & 0xFFFFFFFF
        story.append(DocumentFactory._make_image_flowable(2.5, 1.5, img_seed))
        story.append(Spacer(1, 0.05 * inch))
        caption_style = ParagraphStyle(
            "Caption", parent=styles["Normal"], fontSize=8,
            alignment=TA_CENTER,
        )
        story.append(Paragraph(
            f"Figure {page_num}.1 &mdash; {topic} heatmap (seed {img_seed})",
            caption_style,
        ))
        story.append(Spacer(1, 0.1 * inch))

        tbl_seed = hash((doc_id, page_num, "dtbl")) & 0xFFFFFFFF
        story.append(DocumentFactory._make_data_table(
            random.randint(3, 6), random.randint(4, 6), tbl_seed))

    # ------------------------------------------------------------------
    # PDF creation
    # ------------------------------------------------------------------

    @staticmethod
    def create_pdf(
        doc_id: int,
        filename: str,
        pages: int = 2,
        profile: str = "simple",
    ) -> bytes:
        """Create a PDF document with the given number of pages and profile.

        Uses ReportLab to generate a real PDF binary. Falls back to a plain
        text byte string when ReportLab is not installed (useful for unit
        tests that do not need a real PDF).

        Args:
            doc_id: Numeric identifier embedded in the document.
            filename: Filename string embedded in the document title.
            pages: Number of pages to generate.
            profile: Content profile — ``"simple"`` (text only) or
                ``"complex"`` (tables, images, charts).

        Returns:
            Raw PDF bytes.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
            )

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()

            topic = random.choice(DocumentFactory.TOPICS)
            unique_id = "".join(
                random.choices(string.ascii_letters + string.digits, k=16)
            )

            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                spaceAfter=30,
            )

            story = []
            story.append(
                Paragraph(f"Stress Test Document #{doc_id}", title_style)
            )
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(
                f"Topic: {topic} | Pages: {pages} | "
                f"Profile: {profile} | UID: {unique_id}",
                styles["Normal"],
            ))
            story.append(Spacer(1, 0.2 * inch))

            page_builder = (
                DocumentFactory._build_complex_page
                if profile == "complex"
                else DocumentFactory._build_simple_page
            )

            for page_num in range(1, pages + 1):
                if page_num > 1:
                    story.append(PageBreak())
                page_builder(story, styles, doc_id, page_num, topic)

            story.append(Spacer(1, 0.3 * inch))
            story.append(
                Paragraph(
                    f"Unique ID: {time.time()}-{doc_id}-"
                    f"{random.randint(10000, 99999)}",
                    styles["Normal"],
                )
            )

            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        except ImportError:
            content = DocumentFactory.generate_content(doc_id)
            return content.encode("utf-8")

    @staticmethod
    def make_filename(doc_id: int, prefix: str = "stress_test_doc") -> str:
        """Return a standardised filename for a test document.

        Args:
            doc_id: Numeric document index.
            prefix: Filename prefix.

        Returns:
            Filename string, e.g. ``stress_test_doc_001.pdf``.
        """
        return f"{prefix}_{doc_id:03d}.pdf"

    @staticmethod
    def create_batch(
        count: int,
        start_id: int = 1,
        prefix: str = "stress_test_doc",
        pages: Union[int, Tuple[int, int]] = 2,
        profile: str = "simple",
    ) -> List[Tuple[int, str, bytes]]:
        """Create a batch of PDF documents.

        Args:
            count: Number of documents to generate.
            start_id: First document ID (default 1).
            prefix: Filename prefix for all documents in the batch.
            pages: Fixed page count (int) or ``(min, max)`` tuple for
                random page counts per document.
            profile: Content profile passed to ``create_pdf``.

        Returns:
            List of ``(doc_id, filename, pdf_bytes)`` tuples.
        """
        batch = []
        for i in range(start_id, start_id + count):
            filename = DocumentFactory.make_filename(i, prefix)
            doc_pages = (
                random.randint(pages[0], pages[1])
                if isinstance(pages, tuple)
                else pages
            )
            pdf_bytes = DocumentFactory.create_pdf(
                i, filename, pages=doc_pages, profile=profile,
            )
            batch.append((i, filename, pdf_bytes))
        return batch
