import sqlite3

import pandas as pd
import pandas_ta as ta

INPUT_FILE = 'btc_usdc_history.db'
OUTPUT_FILE = 'btc_usdc_features.db'


def add_technical_indicators(df):
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=60)

    df['rsi'] = ta.rsi(df['close'], length=60)

    bb = ta.bbands(df['close'], length=60, std=2)
    df['bb_lower'] = bb.iloc[:,0]
    df['bb_middle'] = bb.iloc[:,1]
    df['bb_upper'] = bb.iloc[:,2]
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

    df['ema_60'] = ta.ema(df['close'], length=60)
    df['ema_240'] = ta.ema(df['close'], length=240)
    df['ema_trend'] = (df['ema_60'] - df['ema_240']) / df['ema_240']

    df['returns'] = df['close'].pct_change()
    df['volume_change'] = df['volume'].pct_change()

    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df
def generate_labels(df,forward_window=60,trend_bound=0.015):

    future_max=df['high'].shift(-forward_window).rolling(forward_window).max()
    future_min=df['low'].shift(-forward_window).rolling(forward_window).min()

    max_percent=(future_max-df['close'])/df['close']
    min_percent=(future_min-df['close'])/df['close']

    df['market_state']=0

    df.loc[max_percent>trend_bound,'market_state']=1 # will increase
    df.loc[min_percent<-trend_bound,'market_state']=2 #will  decrease

    df.dropna(inplace=True)
    df.reset_index(drop=True,inplace=True)

    return df


def main():
    connect_in=None
    connect_out=None
    try:
        connect_in=sqlite3.connect(INPUT_FILE)

        df=pd.read_sql("SELECT * FROM historical_candles",connect_in)


        df=add_technical_indicators(df)
        df=generate_labels(df)

        connect_out=sqlite3.connect(OUTPUT_FILE)
        df.to_sql('features',connect_out,if_exists='replace',index=False)

        print(f"Success. Save {len(df)} rows to {OUTPUT_FILE}")

        print("How much states market (0=consolidation, 1=UP, 2=DOWN")
        print(df['market_state'].value_counts(normalize=True))
    except Exception as e:
        print("ERROR: ",e)
    finally:
        if connect_in:
            connect_in.close()
        if connect_out:
            connect_out.close()

if __name__=="__main__":
    main()



