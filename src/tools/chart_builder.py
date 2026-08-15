"""Chart builder using matplotlib, seaborn, and plotly."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.io as pio
import seaborn as sns
from loguru import logger

matplotlib.use("Agg")


@dataclass
class ChartArtifact:
    """Represents a generated chart file."""

    path: str
    chart_type: str
    title: str
    description: str


class ChartBuilder:
    """Generate charts from DataFrames and save to disk."""

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sns.set_theme(style="whitegrid", palette="husl")

    def _save_path(self, name: str, ext: str = "png") -> str:
        path = self.output_dir / f"{name}.{ext}"
        return str(path)

    def bar_chart(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str = "Bar Chart",
        name: str = "bar_chart",
    ) -> ChartArtifact:
        """Create a bar chart."""
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(data=df, x=x, y=y, ax=ax)
        ax.set_title(title)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        path = self._save_path(name)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        logger.info("Saved bar chart to {}", path)
        return ChartArtifact(path=path, chart_type="bar", title=title, description=f"Bar chart of {y} by {x}")

    def line_chart(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str = "Line Chart",
        name: str = "line_chart",
    ) -> ChartArtifact:
        """Create a line chart."""
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.lineplot(data=df, x=x, y=y, ax=ax, marker="o")
        ax.set_title(title)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        path = self._save_path(name)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        logger.info("Saved line chart to {}", path)
        return ChartArtifact(path=path, chart_type="line", title=title, description=f"Line chart of {y} over {x}")

    def pie_chart(
        self,
        df: pd.DataFrame,
        labels: str,
        values: str,
        title: str = "Pie Chart",
        name: str = "pie_chart",
    ) -> ChartArtifact:
        """Create a pie chart."""
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.pie(df[values], labels=df[labels], autopct="%1.1f%%", startangle=90)
        ax.set_title(title)
        plt.tight_layout()
        path = self._save_path(name)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        logger.info("Saved pie chart to {}", path)
        return ChartArtifact(path=path, chart_type="pie", title=title, description=f"Pie chart of {values} by {labels}")

    def scatter_plot(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        title: str = "Scatter Plot",
        name: str = "scatter_plot",
        hue: str | None = None,
    ) -> ChartArtifact:
        """Create a scatter plot."""
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.scatterplot(data=df, x=x, y=y, hue=hue, ax=ax, alpha=0.7)
        ax.set_title(title)
        plt.tight_layout()
        path = self._save_path(name)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        logger.info("Saved scatter plot to {}", path)
        return ChartArtifact(path=path, chart_type="scatter", title=title, description=f"Scatter plot of {y} vs {x}")

    def histogram(
        self,
        df: pd.DataFrame,
        column: str,
        title: str = "Histogram",
        name: str = "histogram",
        bins: int = 30,
    ) -> ChartArtifact:
        """Create a histogram."""
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(data=df, x=column, bins=bins, ax=ax, kde=True)
        ax.set_title(title)
        plt.tight_layout()
        path = self._save_path(name)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        logger.info("Saved histogram to {}", path)
        return ChartArtifact(path=path, chart_type="histogram", title=title, description=f"Histogram of {column}")

    def plotly_interactive(
        self,
        df: pd.DataFrame,
        chart_type: str,
        x: str,
        y: str,
        title: str = "Interactive Chart",
        name: str = "interactive_chart",
        **kwargs: Any,
    ) -> ChartArtifact:
        """Create an interactive Plotly chart and save as HTML."""
        chart_funcs = {
            "bar": px.bar,
            "line": px.line,
            "scatter": px.scatter,
            "histogram": px.histogram,
        }
        func = chart_funcs.get(chart_type, px.bar)
        fig = func(df, x=x, y=y, title=title, **kwargs)
        path = self._save_path(name, ext="html")
        pio.write_html(fig, path)
        logger.info("Saved interactive chart to {}", path)
        return ChartArtifact(path=path, chart_type=f"plotly_{chart_type}", title=title, description=f"Interactive {chart_type} chart")
