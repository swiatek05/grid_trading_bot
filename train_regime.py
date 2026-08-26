import sqlite3
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import joblib

INPUT_DB="btc_usdc_features_15m.db"
OUTPUT_REGIME_MODEL="regime_kmeans.joblib"

def main():
    connection=sqlite3.connect(INPUT_DB)
    df=pd.read_sql("SELECT * FROM features",connection)
    connection.close()

    if df.empty:
        print("Lack of data")
        return

    df['atr_percent']=(df['atr']/df['close'])*100
    df['log_atr_percent']=np.log1p(df['atr_percent'])


    clustering_features=['log_atr_percent','bb_width']
    X=df[clustering_features].dropna()

    scaler=StandardScaler()
    X_scaled=scaler.fit_transform(X)

    print("Training k-means..")
    kmeans=KMeans(n_clusters=3,random_state=42,n_init=20)
    kmeans.fit(X_scaled)

    centers=kmeans.cluster_centers_[:,0]
    sorted=np.argsort(centers)

    mapping_label={
        sorted[0]: 0,
        sorted[1]: 1,
        sorted[2]: 2
    }

    regime_data={
        'model': kmeans,
        'scaler': scaler,
        'mapping': mapping_label,
        'features': clustering_features
    }

    joblib.dump(regime_data,OUTPUT_REGIME_MODEL)
    print(f"Success.Regime model was saved as {OUTPUT_REGIME_MODEL}")

if __name__=="__main__":
    main()