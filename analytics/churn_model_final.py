import sqlite3
import json
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

from sklearn.model_selection import train_test_split, cross_validate, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, recall_score, classification_report, confusion_matrix, make_scorer

# ---------- Paths ----------
DB_PATH = "database/competitor_data.db"
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)
PIPELINE_PATH = MODEL_DIR / "churn_pipeline.pkl"
MODEL_CARD_PATH = MODEL_DIR / "model_card.json"

# ---------- Load data ----------
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("SELECT * FROM customer_churn_features", conn)
conn.close()

feature_cols = ["recency_days", "frequency", "monetary_avg", "tenure_days", "purchase_rhythm", "recent_activity"]
target_col = "churned"

X = df[feature_cols]
y = df[target_col]

# ---------- Train/test split (stratified) ----------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ---------- Cross-validation on training set ----------
pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42))
])

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scoring = {
    "accuracy": "accuracy",
    "recall_churned": make_scorer(recall_score, pos_label=1)
}
cv_scores = cross_validate(pipeline, X_train, y_train, cv=cv, scoring=scoring, return_train_score=False)

acc_mean = np.mean(cv_scores["test_accuracy"])
acc_std = np.std(cv_scores["test_accuracy"])
recall_mean = np.mean(cv_scores["test_recall_churned"])
recall_std = np.std(cv_scores["test_recall_churned"])

print("=== CROSS-VALIDATION (5-fold, training set) ===")
print(f"Accuracy: {acc_mean:.3f} ± {acc_std:.3f}")
print(f"Churn recall: {recall_mean:.3f} ± {recall_std:.3f}")

# ---------- Fit final pipeline on full training data ----------
pipeline.fit(X_train, y_train)
y_pred = pipeline.predict(X_test)

print("\n=== FINAL TEST SET EVALUATION ===")
print(f"Accuracy: {accuracy_score(y_test, y_pred):.3f}")
print(f"Churn recall: {recall_score(y_test, y_pred, pos_label=1):.3f}")
print("Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Retained", "Churned"]))
print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))

# ---------- Feature importance (from logistic regression) ----------
# Get the logistic regression model from pipeline
logreg = pipeline.named_steps["model"]
# Feature names after scaling: same order as feature_cols
coefficients = logreg.coef_[0]
feature_importance = pd.DataFrame({
    "feature": feature_cols,
    "coefficient": coefficients
})
feature_importance["abs_coefficient"] = feature_importance["coefficient"].abs()
feature_importance = feature_importance.sort_values("abs_coefficient", ascending=False)

print("\n=== FEATURE IMPORTANCE (coefficients per standard deviation) ===")
print(feature_importance[["feature", "coefficient"]].to_string(index=False))

# ---------- Save pipeline ----------
joblib.dump(pipeline, PIPELINE_PATH)
print(f"\nPipeline saved to {PIPELINE_PATH}")

# ---------- Create model card ----------
model_card = {
    "training_date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    "dataset_size": len(df),
    "train_size": len(X_train),
    "test_size": len(X_test),
    "churn_rate_total": float(y.mean()),
    "churn_rate_train": float(y_train.mean()),
    "churn_rate_test": float(y_test.mean()),
    "cv_accuracy_mean": float(acc_mean),
    "cv_accuracy_std": float(acc_std),
    "cv_recall_churned_mean": float(recall_mean),
    "cv_recall_churned_std": float(recall_std),
    "test_accuracy": float(accuracy_score(y_test, y_pred)),
    "test_recall_churned": float(recall_score(y_test, y_pred, pos_label=1)),
    "feature_order": feature_cols,
    "label_definition": "churn = no order in the 90-day window after snapshot",
    "coefficient_story": {
        f: float(c) for f, c in zip(feature_cols, coefficients)
    },
    "risk_tiering_note": "Risk flags in scoring are percentile-based (top 15% HIGH, next 25% MEDIUM) because absolute probabilities from a small synthetic model are uncalibrated. This is a documented business decision."
}
with open(MODEL_CARD_PATH, "w") as f:
    json.dump(model_card, f, indent=2)
print(f" Model card saved to {MODEL_CARD_PATH}")

# ---------- Smoke test: reload and compare ----------
loaded_pipeline = joblib.load(PIPELINE_PATH)
# Sample 5 customers from test set (or any rows)
sample_indices = X_test.index[:5]
sample_features = X_test.loc[sample_indices]
# Predict probabilities from in-memory and loaded pipeline
probs_memory = pipeline.predict_proba(sample_features)[:, 1]
probs_loaded = loaded_pipeline.predict_proba(sample_features)[:, 1]

print("\n=== SMOKE TEST (churn risk probabilities on 5 samples) ===")
for i, idx in enumerate(sample_indices):
    print(f"Customer {idx}: in-memory {probs_memory[i]:.4f}, loaded {probs_loaded[i]:.4f}")

if np.allclose(probs_memory, probs_loaded):
    print("Loaded pipeline matches in-memory predictions.")
else:
    print("Mismatch! Do not deploy.")