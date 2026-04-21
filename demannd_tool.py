import streamlit as st
import pandas as pd
import zipfile
import io

st.title("デマンドデータ月別変換ツール")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type="csv")

if uploaded_file:

    # =============================
    # 読み込み
    # =============================
    df = pd.read_csv(uploaded_file, encoding="cp932")

    date_col = df.columns[2]
    time_cols = df.columns[7:54]

    df = df[[date_col] + list(time_cols)]

    # =============================
    # melt
    # =============================
    df_long = df.melt(
        id_vars=[date_col],
        var_name="# time",
        value_name="消費電力[kW]"
    )

    # =============================
    # datetime作成
    # =============================
    df_long["datetime"] = pd.to_datetime(
        df_long[date_col].astype(str) + " " + df_long["# time"]
    )

    df_long = df_long.sort_values("datetime")

    # =============================
    # ZIP作成
    # =============================
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zf:

        for month in range(1, 13):

            df_month = df_long[
                df_long["datetime"].dt.month == month
            ]

            if df_month.empty:
                continue

            year = df_month["datetime"].dt.year.iloc[0]

            # 表示用time
            df_month["# time"] = df_month["datetime"].dt.strftime("%Y/%m/%d %H:%M")

            csv_buffer = io.BytesIO()

            df_month[["# time", "消費電力[kW]"]].to_csv(
                csv_buffer,
                index=False,
                encoding="utf-8-sig"  
            )

            filename = f"{year}年{month:02d}月.csv"

            zf.writestr(filename, csv_buffer.getvalue())

    # =============================
    # ダウンロードボタン
    # =============================
    st.download_button(
        label="月別CSVをまとめてダウンロード",
        data=zip_buffer.getvalue(),
        file_name="monthly_data.zip",
        mime="application/zip"
    )