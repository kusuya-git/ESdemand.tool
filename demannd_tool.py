import streamlit as st
import pandas as pd
import zipfile
import io

st.title("デマンドデータ月別変換ツール")

uploaded_files = st.file_uploader(
    "CSVまたはExcelファイルをアップロード（複数可）",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True
)

def read_file(f):
    name = f.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(f, header=None, engine="openpyxl")
    else:
        for encoding in ["cp932", "shift_jis", "utf-8", "utf-8-sig", "latin1"]:
            try:
                f.seek(0)
                return pd.read_csv(f, encoding=encoding, header=None)
            except:
                continue
        raise ValueError("文字コードを自動判定できませんでした")

if uploaded_files:

    first_file = uploaded_files[0]
    df_raw = read_file(first_file)

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
        with col1:
            st.markdown("**日付の開始位置**")
            date_row = st.number_input("日付の開始行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
            date_col_idx = st.number_input("日付の開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)
        with col2:
            st.markdown("**時間ヘッダの位置**（この行の次の行からデータを取得）")
            time_header_row = st.number_input("時間ヘッダの行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
            time_col_idx = st.number_input("時間データの開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)
    else:
        with col1:
            st.markdown("**時間ラベルの位置**")
            time_label_col = st.number_input("時間ラベルの列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)
            time_data_start_row = st.number_input("時間データの開始行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
        with col2:
            st.markdown("**日付の開始位置**")
            date_row_idx = st.number_input("日付の行（0始まり）", min_value=0, max_value=len(df_raw)-1, value=0)
            date_col_start = st.number_input("日付の開始列（0始まり）", min_value=0, max_value=len(df_raw.columns)-1, value=0)

    st.subheader("③-② 開始年を入力")
    st.caption("日付に年情報がない場合や、年またぎデータの場合に使用します")
    use_manual_year = st.checkbox("年を手動で指定する")
    start_year = None
    if use_manual_year:
        start_year = st.number_input("データの開始年", min_value=2000, max_value=2100, value=2024)

    st.subheader("③-確認 指定位置のプレビュー")
    col_a, col_b = st.columns(2)

    if "縦：日付　横：時間" in layout:
        with col_a:
            st.markdown("**日付列の内容（先頭10件）**")
            preview = df_raw.iloc[int(date_row):int(date_row)+10, int(date_col_idx)]
            st.dataframe(preview.reset_index(drop=True).rename("日付"), use_container_width=True)
        with col_b:
            st.markdown("**時間ヘッダ行の内容（先頭10件）**")
            preview = df_raw.iloc[int(time_header_row), int(time_col_idx):int(time_col_idx)+10]
            st.dataframe(preview.reset_index(drop=True).rename("時間ヘッダ"), use_container_width=True)
    else:
        with col_a:
            st.markdown("**時間ラベル列の内容（先頭10件）**")
            preview = df_raw.iloc[int(time_data_start_row):int(time_data_start_row)+10, int(time_label_col)]
            st.dataframe(preview.reset_index(drop=True).rename("時間ラベル"), use_container_width=True)
        with col_b:
            st.markdown("**日付行の内容（先頭10件）**")
            preview = df_raw.iloc[int(date_row_idx), int(date_col_start):int(date_col_start)+10]
            st.dataframe(preview.reset_index(drop=True).rename("日付"), use_container_width=True)

    if st.button("プレビューを確認"):

        times_generated = pd.date_range("00:00", "23:30", freq="30min").strftime("%H:%M").tolist()

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

        all_df = []

        for f in uploaded_files:
            try:
                df_f = read_file(f)

                if "縦：日付　横：時間" in layout:
                    dates = df_f.iloc[int(date_row):, int(date_col_idx)].reset_index(drop=True)
                    n_rows = len(dates)
                    values = df_f.iloc[int(time_header_row)+1:int(time_header_row)+1+n_rows, int(time_col_idx):int(time_col_idx)+48].reset_index(drop=True)
                    values.columns = times_generated[:values.shape[1]]
                    df_data = values.copy()
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

                else:
                    # 日付を行方向に取得
                    dates_raw = df_f.iloc[int(date_row_idx), int(date_col_start):].reset_index(drop=True)

                    # 数値データ取得（時間ラベル列の次の列から）
                    data_col_start = int(date_col_start)
                    n_cols = len(dates_raw)
                    values = df_f.iloc[int(time_data_start_row):int(time_data_start_row)+48, data_col_start:data_col_start+n_cols].reset_index(drop=True)

                    # 日付をパース（年またぎ対応）
                    if use_manual_year:
                        dates_parsed = parse_dates_with_year(dates_raw.astype(str), int(start_year))
                    else:
                        dates_parsed = pd.to_datetime(dates_raw.astype(str), format="mixed", errors="coerce")

                    # 時間ラベルを生成して各列×各時間でDataFrame作成
                    records = []
                    for col_i, date_val in enumerate(dates_parsed):
                        if pd.isna(date_val):
                            continue
                        for row_i, time_val in enumerate(times_generated[:values.shape[0]]):
                            records.append({
                                "日付": date_val,
                                "# time": time_val,
                                "消費電力[kW]": values.iloc[row_i, col_i]
                            })
                    df_long = pd.DataFrame(records)

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
