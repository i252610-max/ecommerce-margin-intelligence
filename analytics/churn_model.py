import sqlite3
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

DB_PATH = "database/competitor_data.db"

def run_churn_model():
    """Train and evaluate churn prediction model with class imbalance handling."""
    # ---------- Step 2: Load and prepare data ----------
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM customer_churn_features", conn)
    conn.close()

    feature_cols = ["recency_days", "frequency", "monetary_avg", "tenure_days", "purchase_rhythm", "recent_activity"]
    target_col = "churned"

    X = df[feature_cols]
    y = df[target_col]

    # ---------- Step 3: Train/test split with stratification ----------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
    print(f"Train churn rate: {y_train.mean():.2%}, Test churn rate: {y_test.mean():.2%}")

    # ---------- Step 4: Scale without leakage ----------
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)   # fit only on training
    X_test_scaled = scaler.transform(X_test)         # transform test using train stats

    # ---------- Step 5: Baseline model (no class weighting) ----------
    baseline = LogisticRegression(max_iter=1000, random_state=42)
    baseline.fit(X_train_scaled, y_train)
    y_pred_base = baseline.predict(X_test_scaled)

    print("\n=== BASELINE MODEL (no class weighting) ===")
    print(f"Accuracy: {accuracy_score(y_test, y_pred_base):.3f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred_base, target_names=["Retained", "Churned"]))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred_base))

    # ---------- Step 6: Balanced model ----------
    balanced = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    balanced.fit(X_train_scaled, y_train)
    y_pred_bal = balanced.predict(X_test_scaled)

    print("\n=== BALANCED MODEL (class_weight='balanced') ===")
    print(f"Accuracy: {accuracy_score(y_test, y_pred_bal):.3f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred_bal, target_names=["Retained", "Churned"]))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred_bal))

    # ---------- Step 7: Interpret coefficients ----------
    coefficients = pd.DataFrame({
        "feature": feature_cols,
        "coefficient": balanced.coef_[0]
    })
    coefficients["abs_coefficient"] = coefficients["coefficient"].abs()
    coefficients = coefficients.sort_values("abs_coefficient", ascending=False)
    print("\n=== FEATURE IMPORTANCE (absolute coefficient) ===")
    print(coefficients[["feature", "coefficient"]].to_string(index=False))

    recency_coef = coefficients.loc[coefficients["feature"] == "recency_days", "coefficient"].values[0]
    print(f"\nModel story: Each additional day of recency changes log-odds of churn by {recency_coef:.4f}.")
    print("A positive coefficient means higher recency (more days since last purchase) increases churn probability.")

if __name__ == "__main__":
    run_churn_model()