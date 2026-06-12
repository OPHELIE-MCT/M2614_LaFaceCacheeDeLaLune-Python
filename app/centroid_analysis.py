from __future__ import annotations
from sklearn.preprocessing import normalize
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")


FEATURE_NAMES = [f"channel{index}" for index in range(1, 11)]
CLASS_ORDER = ["orange", "purple", "blue", "green", "yellow", "pink", "red"]
CLASS_COLOR_MAP = {
    "orange": "#ff8c00",
    "purple": "#7b2cbf",
    "blue": "#1f77b4",
    "green": "#2ca02c",
    "yellow": "#ffe600",
    "pink": "#e75480",
    "red": "#ff0000",
}
UNKNOWN_DISTANCE_PERCENTILE = 95
EXPECTED_HEADER = ["color_name", *FEATURE_NAMES]


def load_labeled_samples(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing calibration CSV at {path}. Capture samples first."
        )

    labels: list[str] = []
    rows: list[list[float]] = []

    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != EXPECTED_HEADER:
            raise ValueError(
                f"Unexpected CSV header {reader.fieldnames!r}. Expected {EXPECTED_HEADER!r}."
            )

        for row in reader:
            color_name = row["color_name"].strip().lower()
            if color_name not in CLASS_ORDER:
                raise ValueError(
                    f"Unsupported color label {color_name!r} in {path}.")

            sample = [float(row[feature_name])
                      for feature_name in FEATURE_NAMES]
            labels.append(color_name)
            rows.append(sample)

    if not rows:
        raise ValueError("The calibration CSV is empty.")

    X_values = np.asarray(rows, dtype=float)
    y_labels = np.asarray(labels, dtype=object)

    if X_values.ndim != 2:
        raise ValueError(
            f"Expected a 2D feature matrix, got shape {X_values.shape}.")
    if X_values.shape[1] != 10:
        raise ValueError(f"Expected 10 features, got {X_values.shape[1]}.")

    missing_classes = [
        label for label in CLASS_ORDER if label not in set(y_labels.tolist())]
    if missing_classes:
        raise ValueError(
            "Missing labeled classes in the CSV: " + ", ".join(missing_classes))

    return X_values, y_labels


def format_float(value: float) -> str:
    return f"{value:.8f}f"


def build_cpp_code(centroids: np.ndarray, unknown_threshold: float) -> str:
    centroid_rows = [
        "    {" + ", ".join(format_float(value) for value in row) + "}"
        for row in centroids
    ]

    lines: list[str] = ["constexpr const char* kClassNames[kClassCount] = {"]
    for label in CLASS_ORDER:
        lines.append(f'    "{label}",')
    lines.append("};")
    lines.append("")
    lines.append(
        "constexpr float kClassCentroids[kClassCount][kFeatureCount] = {")
    for index, row in enumerate(centroid_rows):
        suffix = "," if index < len(centroid_rows) - 1 else ""
        lines.append(f"{row}{suffix}")
    lines.append("};")
    lines.append("")
    lines.append(
        f"constexpr float kUnknownThreshold = {unknown_threshold:.8f}f;")
    return "\n".join(lines)


def run_centroid_analysis(csv_path: Path, plots_dir: Path) -> dict[str, object]:
    X_values, labels = load_labeled_samples(csv_path)
    X_norm = normalize(X_values, norm="l2")
    class_to_id = {label: index for index, label in enumerate(CLASS_ORDER)}
    class_ids = np.array([class_to_id[label] for label in labels])
    class_sizes = {label: int(np.sum(labels == label))
                   for label in CLASS_ORDER}
    centroids = np.vstack([X_norm[labels == label].mean(axis=0)
                          for label in CLASS_ORDER])
    assigned_distances = np.linalg.norm(X_norm - centroids[class_ids], axis=1)
    unknown_threshold = float(np.percentile(
        assigned_distances, UNKNOWN_DISTANCE_PERCENTILE))

    if len(np.unique(class_ids)) > 1 and len(X_norm) > len(CLASS_ORDER):
        silhouette_value = float(silhouette_score(X_norm, class_ids))
    else:
        silhouette_value = float("nan")

    plots_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")

    plot_links: list[dict[str, str]] = []

    distribution_path = plots_dir / "class_distribution.png"
    plt.figure(figsize=(8, 4))
    sns.countplot(x=labels, hue=labels, order=CLASS_ORDER,
                  palette=CLASS_COLOR_MAP, legend=False)
    plt.title("Samples per labeled class")
    plt.xlabel("Class")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(distribution_path, dpi=180)
    plt.close()
    plot_links.append({"label": "Class distribution",
                      "href": "/static/generated/analysis/class_distribution.png"})

    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_norm)
    centroids_pca = pca.transform(centroids)
    pca_path = plots_dir / "pca_projection.png"
    plt.figure(figsize=(9, 7))
    for class_index, label in enumerate(CLASS_ORDER):
        members = labels == label
        plt.scatter(
            X_pca[members, 0],
            X_pca[members, 1],
            s=45,
            alpha=0.45,
            color=CLASS_COLOR_MAP[label],
            edgecolor="none",
            label=label,
        )
        plt.scatter(
            centroids_pca[class_index, 0],
            centroids_pca[class_index, 1],
            s=240,
            marker="X",
            color=CLASS_COLOR_MAP[label],
            edgecolor="black",
            linewidth=0.8,
        )
    plt.title("PCA projection of normalized labeled samples")
    plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)")
    plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)")
    plt.legend(title="Class", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(pca_path, dpi=180)
    plt.close()
    plot_links.append({"label": "PCA projection",
                      "href": "/static/generated/analysis/pca_projection.png"})

    heatmap_path = plots_dir / "centroid_profiles.png"
    plt.figure(figsize=(11, 4.5))
    sns.heatmap(
        centroids,
        cmap="mako",
        xticklabels=FEATURE_NAMES,
        yticklabels=CLASS_ORDER,
        cbar_kws={"label": "mean normalized feature value"},
    )
    plt.title("Class centroid profiles across the 10 AS7341 channels")
    plt.xlabel("Feature")
    plt.ylabel("Class")
    plt.tight_layout()
    plt.savefig(heatmap_path, dpi=180)
    plt.close()
    plot_links.append({"label": "Centroid profiles",
                      "href": "/static/generated/analysis/centroid_profiles.png"})

    similarity_matrix = cosine_similarity(centroids)
    similarity_path = plots_dir / "cosine_similarity.png"
    plt.figure(figsize=(7, 6))
    sns.heatmap(
        similarity_matrix,
        annot=True,
        fmt=".3f",
        cmap="viridis",
        xticklabels=CLASS_ORDER,
        yticklabels=CLASS_ORDER,
    )
    plt.title("Centroid cosine similarity")
    plt.tight_layout()
    plt.savefig(similarity_path, dpi=180)
    plt.close()
    plot_links.append({"label": "Cosine similarity",
                      "href": "/static/generated/analysis/cosine_similarity.png"})

    cpp_code = build_cpp_code(centroids, unknown_threshold)
    return {
        "cpp_code": cpp_code,
        "plot_links": plot_links,
        "unknown_threshold": unknown_threshold,
        "silhouette_score": None if np.isnan(silhouette_value) else silhouette_value,
        "sample_count": int(len(X_values)),
        "class_sizes": class_sizes,
    }
