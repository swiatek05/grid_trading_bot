import sqlite3

import joblib
import pandas as pd
import numpy as np
from pandas import read_sql
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import make_classification
from sklearn.metrics import accuracy_score, classification_report

INPUT_NAME="btc_usdc_features_15m.db"
RESULT_NAME_MODEL="grid_model_predict_15m.joblib"

FEATURE_COLUMNS = [
    'atr', 'rsi', 'bb_width', 'ema_trend',
    'returns', 'volume_change'
]

TARGET_COLUMS="market_state"

def train_and_return_result():
    connection=sqlite3.connect(INPUT_NAME)
    df=read_sql("SELECT * from features",connection)
    connection.close()

    if df.empty:
        print("Lack of data")
    print(f"Loaded {len(df)} rows")

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)

    X=df[FEATURE_COLUMNS]  #indicators
    Y=df[TARGET_COLUMS]

    split_data_index=int(len(df)*0.8)

    X_train,X_test=X.iloc[:split_data_index],X.iloc[split_data_index:]
    Y_train,Y_test=Y.iloc[:split_data_index],Y.iloc[split_data_index:]

    print(f"{len(X_train)} rows to train (80% data)")
    print(f"{len(X_test)} row to test (20% data)")

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=12,
        min_samples_leaf=30,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    print("Training ...")
    model.fit(X_train,Y_train)

    Y_pred = model.predict(X_test)

    acc = accuracy_score(Y_test, Y_pred)

    print(f"Accuracy: {acc}")

    print(classification_report(Y_test, Y_pred, target_names=['0-Consolidation', '1-grow', '2-decrease']))

    joblib.dump(model, RESULT_NAME_MODEL)

if __name__=="__main__":
    train_and_return_result()

