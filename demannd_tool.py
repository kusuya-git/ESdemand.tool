import streamlit as st
import pandas as pd
import zipfile
import io

st.title("デマンドデータ月別変換ツール")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type="csv")

if uploaded_file:

    # =============================
    # 読み込み（全列・全行）
    # =============================
    try:
        df_raw = pd.read_csv(uploaded_file, encoding="cp932", header=None)
    except:
        uploaded_file.seek(0)
        df_raw = pd.read_csv(uploaded_file, encoding="utf-8", header=None)

    st.subheader("① データの向きを選択")
    layout = st.radio(
        "データの構造を選んでください",
        ["縦：日付　横：時間（各行が1日分）", "縦：時間　横：日付（各列が1日分）"]
    )

    st.subheader("② 生データプレビュー（行・列番号付き）")
    st.caption("※ 行番号・列番号は0始まりです")

    df_display = df_raw.copy()
    df_display.columns = [f"列{i}" for i in range(len(df_raw.columns))]
    df_display.index = [f"行{i}" for i in range(len(df_raw))]
    st.dataframe(df_display, use_container_width=True)

    st.subheader("③ 日付・時間の開始位置を指定")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**日付の開始位置**")
        date_row = st.number_input("日付の開始行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
        date_col_idx = st.number_input("日付の開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)

    with col2:
        st.markdown("**時間データの開始位置**")
        time_data_row = st.number_input("時間データの開始行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
        time_col_idx = st.number_input("時間データの開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)

    # =============================
    # 指定位置のプレビュー
    # =============================
    st.subheader("③-確認 指定位置のプレビュー")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**日付列の内容（先頭10件）**")
        date_preview = df_raw.iloc[int(date_row):int(date_row)+10, int(date_col_idx)]
        st.dataframe(date_preview.reset_index(drop=True).rename("日付"), use_container_width=True)

    with col_b:
        st.markdown("**時間データ列の内容（先頭行）**")
        time_preview = df_raw.iloc[int(time_data_row), int(time_col_idx):int(time_col_idx)+10]
        st.dataframe(time_preview.reset_index(drop=True).rename("時間データ先頭"), use_container_width=True)

    if st.button("プレビューを確認"):

        # 30分刻みの時間ラベルを自動生成
        times_generated = pd.date_range("00:00", "23:30", freq="30min").strftime("%H:%M").tolist()

        # =============================
        # レイアウト別に整形
        # =============================
        if "縦：日付　横：時間" in layout:
            dates = df_raw.iloc[int(date_row):, int(date_col_idx)].reset_index(drop=True)
            n_rows = len(dates)
            # time_data_rowは列名行なので+1してデータ行から取得
            values = df_raw.iloc[int(time_data_row)+1:int(time_data_row)+1+n_rows, int(time_col_idx):int(time_col_idx)+48].reset_index(drop=True)
            values.columns = times_generated[:values.shape[1]]

            df_data = values.copy()
            df_data.insert(0, "日付", dates.values)

            df_long = df_data.melt(
                id_vars=["日付"],
                var_name="# time",
                value_name="消費電力[kW]"
            )

        else:
            dates = df_raw.iloc[int(date_row), int(date_col_idx):].reset_index(drop=True)
            # time_data_rowは列名行なので+1してデータ行から取得
            values = df_raw.iloc[int(time_data_row)+1:int(time_data_row)+1+48, int(time_col_idx):].reset_index(drop=True)
            values.index = times_generated[:values.shape[0]]

            df_data = values.T.copy()
            df_data.insert(0, "日付", dates.values)

            df_long = df_data.melt(
                id_vars=["日付"],
                var_name="# time",
                value_name="消費電力[kW]"
            )

        # =============================
        # datetime作成
        # =============================
        try:
            df_long["日付"] = pd.to_datetime(df_long["日付"].astype(str), format="mixed")
            df_long["datetime"] = pd.to_datetime(
                df_long["日付"].dt.strftime("%Y/%m/%d") + " " + df_long["# time"].astype(str)
            )
            df_long = df_long.dropna(subset=["datetime"])
            df_long = df_long.sort_values("datetime")

            st.subheader("④ 整形後プレビュー（先頭20行）")
            st.dataframe(df_long[["datetime", "消費電力[kW]"]].head(20), use_container_width=True)

            st.session_state["df_long"] = df_long
            st.success("プレビューOKなら下のボタンでダウンロードできます！")

        except Exception as e:
            st.error(f"datetime変換エラー：{e}\n日付・時間の位置指定を見直してください。")

    # =============================
    # ダウンロード
    # =============================
    if "df_long" in st.session_state:

        df_long = st.session_state["df_long"]

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for month in range(1, 13):
                df_month = df_long[df_long["datetime"].dt.month == month].copy()

                if df_month.empty:
                    continue

                year = df_month["datetime"].dt.year.iloc[0]
                df_month["# time"] = df_month["datetime"].dt.strftime("%Y/%m/%d %H:%M")

                csv_buffer = io.BytesIO()
                df_month[["# time", "消費電力[kW]"]].to_csv(
                    csv_buffer,
                    index=False,
                    encoding="utf-8-sig"
                )

                filename = f"{year}年{month:02d}月.csv"
                zf.writestr(filename, csv_buffer.getvalue())

        st.download_button(
            label="月別CSVをまとめてダウンロード",
            data=zip_buffer.getvalue(),
            file_name="monthly_data.zip",
            mime="application/zip"
        )
