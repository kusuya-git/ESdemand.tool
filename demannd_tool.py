import streamlit as st
import pandas as pd
import zipfile
import io

st.title("デマンドデータ月別変換ツール")

uploaded_files = st.file_uploader("CSVファイルをアップロード（複数可）", type="csv", accept_multiple_files=True)

if uploaded_files:

    # =============================
    # 最初のファイルでプレビュー
    # =============================
    first_file = uploaded_files[0]

    try:
        df_raw = pd.read_csv(first_file, encoding="cp932", header=None)
    except:
        first_file.seek(0)
        df_raw = pd.read_csv(first_file, encoding="utf-8", header=None)

    st.caption(f"※ プレビューは「{first_file.name}」を使用しています")

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

    if "縦：日付　横：時間" in layout:
        label_left = "日付"
        label_right = "時間データ"
    else:
        label_left = "時間データ"
        label_right = "日付"

    with col1:
        st.markdown(f"**{label_left}の開始位置**")
        date_row = st.number_input(f"{label_left}の開始行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
        date_col_idx = st.number_input(f"{label_left}の開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)

    with col2:
        st.markdown(f"**{label_right}の開始位置**")
        time_data_row = st.number_input(f"{label_right}の開始行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
        time_col_idx = st.number_input(f"{label_right}の開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)

    st.subheader("③-② 開始年を入力")
    st.caption("日付に年情報がない場合や、年またぎデータの場合に使用します")
    use_manual_year = st.checkbox("年を手動で指定する")
    start_year = None
    if use_manual_year:
        start_year = st.number_input("データの開始年", min_value=2000, max_value=2100, value=2024)

    st.subheader("③-確認 指定位置のプレビュー")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(f"**{label_left}列の内容（先頭10件）**")
        date_preview = df_raw.iloc[int(date_row):int(date_row)+10, int(date_col_idx)]
        st.dataframe(date_preview.reset_index(drop=True).rename(label_left), use_container_width=True)

    with col_b:
        st.markdown(f"**{label_right}列の内容（先頭行）**")
        time_preview = df_raw.iloc[int(time_data_row), int(time_col_idx):int(time_col_idx)+10]
        st.dataframe(time_preview.reset_index(drop=True).rename(label_right), use_container_width=True)

    if st.button("プレビューを確認"):

        times_generated = pd.date_range("00:00", "23:30", freq="30min").strftime("%H:%M").tolist()

        # =============================
        # 年付与関数
        # =============================
        def parse_dates_with_year(date_series, start_year):
            parsed = []
            current_year = start_year
            prev_month = None
            for d in date_series:
                try:
                    dt = pd.to_datetime(f"{current_year}/{d}", format="mixed")
                    if prev_month is not None and dt.month < prev_month:
                        current_year += 1
                        dt = pd.to_datetime(f"{current_year}/{d}", format="mixed")
                    prev_month = dt.month
                    parsed.append(dt)
                except:
                    parsed.append(pd.NaT)
            return pd.Series(parsed)

        # =============================
        # 全ファイル処理
        # =============================
        all_df = []

        for f in uploaded_files:
            try:
                try:
                    df_f = pd.read_csv(f, encoding="cp932", header=None)
                except:
                    f.seek(0)
                    df_f = pd.read_csv(f, encoding="utf-8", header=None)

                if "縦：日付　横：時間" in layout:
                    dates = df_f.iloc[int(date_row):, int(date_col_idx)].reset_index(drop=True)
                    n_rows = len(dates)
                    values = df_f.iloc[int(time_data_row)+1:int(time_data_row)+1+n_rows, int(time_col_idx):int(time_col_idx)+48].reset_index(drop=True)
                    values.columns = times_generated[:values.shape[1]]
                    df_data = values.copy()
                    df_data.insert(0, "日付", dates.values)
                else:
                    dates = df_f.iloc[int(time_data_row), int(time_col_idx):].reset_index(drop=True)
                    n_cols = len(dates)
                    values = df_f.iloc[int(date_row)+1:int(date_row)+1+48, int(date_col_idx):int(date_col_idx)+n_cols].reset_index(drop=True)
                    values.index = times_generated[:values.shape[0]]
                    df_data = values.T.copy()
                    df_data.insert(0, "日付", dates.values)

                df_long = df_data.melt(
                    id_vars=["日付"],
                    var_name="# time",
                    value_name="消費電力[kW]"
                )

                if use_manual_year:
                    df_long["日付"] = parse_dates_with_year(df_long["日付"].astype(str), int(start_year))
                else:
                    df_long["日付"] = pd.to_datetime(df_long["日付"].astype(str), format="mixed", errors="coerce")

                df_long = df_long.dropna(subset=["日付"])

                df_long["datetime"] = pd.to_datetime(
                    df_long["日付"].dt.strftime("%Y/%m/%d") + " " + df_long["# time"].astype(str)
                )
                df_long = df_long.dropna(subset=["datetime"])
                all_df.append(df_long)

            except Exception as e:
                st.warning(f"{f.name} の処理中にエラー：{e}")

        if all_df:
            df_all = pd.concat(all_df).sort_values("datetime").drop_duplicates(subset=["datetime"])

            st.subheader("④ 整形後プレビュー（先頭20行）")
            st.dataframe(df_all[["datetime", "消費電力[kW]"]].head(20), use_container_width=True)
            st.success(f"{len(uploaded_files)}ファイル処理完了！プレビューOKなら下のボタンでダウンロードできます！")

            st.session_state["df_long"] = df_all
        else:
            st.error("処理できたファイルがありませんでした。設定を見直してください。")

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
