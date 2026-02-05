import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import locale

# 한국어 로케일 설정을 시도
try:
    locale.setlocale(locale.LC_TIME, 'ko_KR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'korean')
    except locale.Error:
        st.warning("한국어 로케일을 설정할 수 없습니다. 달력이 영어로 표시될 수 있습니다.")

# ------------------------------------------------------------------
# 1. 페이지 기본 설정
# ------------------------------------------------------------------
st.set_page_config(page_title="주간 영업 실적 대시보드", layout="wide")

st.title("📊 주간 영업 실적 현황")
st.markdown("매주 업데이트되는 영업 실적 데이터를 조회합니다.")

# ------------------------------------------------------------------
# 2. 고정된 파일 읽어오기 (핵심 변경!)
# ------------------------------------------------------------------
TARGET_FILE = 'data.csv'

if not os.path.exists(TARGET_FILE):
    st.error(f"⚠️ 데이터 파일이 없습니다!")
    st.info(f"하이웍스에서 다운받은 CSV 파일 이름을 '{TARGET_FILE}'로 변경해서 폴더에 넣어주세요.")
else:
    # 1) 파일 읽기
    try:
        df = pd.read_csv(TARGET_FILE, encoding='cp949')
    except UnicodeDecodeError:
        df = pd.read_csv(TARGET_FILE, encoding='utf-8')

    # 2) 날짜 변환
    if '문의 일자' in df.columns:
        df['문의 일자'] = pd.to_datetime(df['문의 일자'], format='%Y-%m-%d', errors='coerce')
        df['문의년월'] = df['문의 일자'].dt.strftime('%Y-%m')
    
    # 데이터 업데이트 시간 표시 (파일 수정 시간)
    file_time = os.path.getmtime(TARGET_FILE)
    last_update = pd.to_datetime(file_time, unit='s').strftime('%Y-%m-%d %H:%M')
    st.caption(f"📅 데이터 마지막 업데이트: {last_update}")
    
    st.divider()

    # ------------------------------------------------------------------
    # 3. 사이드바 필터
    # ------------------------------------------------------------------
    st.sidebar.header("🔍 조회 필터")

    # (1) 기간 필터
    if '문의 일자' in df.columns:
        # NaT 값을 제거하고 날짜 열을 복사하여 원본 데이터프레임 보존
        df_for_date_filter = df.dropna(subset=['문의 일자']).copy()
        
        if not df_for_date_filter.empty:
            df_for_date_filter['연도'] = df_for_date_filter['문의 일자'].dt.year
            df_for_date_filter['월'] = df_for_date_filter['문의 일자'].dt.month

            min_date = df_for_date_filter['문의 일자'].min()
            max_date = df_for_date_filter['문의 일자'].max()

            filter_type = st.sidebar.radio(
                "기간 필터 유형",
                ('전체 기간', '기간 지정', '연도 지정', '월 지정'),
                horizontal=True
            )

            if filter_type == '기간 지정':
                start_date, end_date = st.sidebar.date_input(
                    "조회 기간", [min_date.date(), max_date.date()], 
                    min_value=min_date.date(), max_value=max_date.date()
                )
                if start_date and end_date:
                    df = df[(df['문의 일자'].dt.date >= start_date) & (df['문의 일자'].dt.date <= end_date)]
            
            elif filter_type == '연도 지정':
                years = sorted(df_for_date_filter['연도'].unique(), reverse=True)
                sel_year = st.sidebar.selectbox("연도 선택", years)
                if sel_year:
                    df = df[df['문의 일자'].dt.year == sel_year]

            elif filter_type == '월 지정':
                col1, col2 = st.sidebar.columns(2)
                years = sorted(df_for_date_filter['연도'].unique(), reverse=True)
                sel_year = col1.selectbox("연도 선택", years)
                
                months = []
                if sel_year:
                    months = sorted(df_for_date_filter[df_for_date_filter['연도'] == sel_year]['월'].unique())
                
                sel_month = col2.selectbox("월 선택", months)
                
                if sel_year and sel_month:
                    df = df[(df['문의 일자'].dt.year == sel_year) & (df['문의 일자'].dt.month == sel_month)]
            
            # '전체 기간'이 선택된 경우, df는 필터링되지 않고 전체 데이터로 유지됩니다.
        else:
            st.sidebar.warning("조회할 날짜 데이터가 없습니다.")


    # (2) 팀/담당자 필터
    if '진행 팀' in df.columns:
        teams = ['전체'] + sorted(list(df['진행 팀'].dropna().unique()))
        sel_team = st.sidebar.selectbox("팀 선택", teams)
        if sel_team != '전체': df = df[df['진행 팀'] == sel_team]

    if '담당자' in df.columns:
        # 콤마로 구분된 담당자를 모두 분리하여 고유한 목록 만들기
        all_managers = set()
        for manager_list in df['담당자'].dropna().unique():
            for manager in manager_list.split(','):
                all_managers.add(manager.strip())
        
        managers = ['전체'] + sorted(list(all_managers))
        sel_manager = st.sidebar.selectbox("담당자 선택", managers)
        
        # '전체'가 아닐 경우, 선택된 담당자 이름을 포함하는 모든 행을 필터링
        if sel_manager != '전체':
            df = df[df['담당자'].str.contains(sel_manager, na=False)]

    # ------------------------------------------------------------------
    # 4. 분석 및 시각화 (탭 구조)
    # ------------------------------------------------------------------
    success_status = ['확정', '진행 완료']
    has_sales_data = '매출액' in df.columns and '마진금액' in df.columns

    # 매출 데이터가 있을 경우, 숫자형으로 변환
    if has_sales_data:
        df['매출액'] = pd.to_numeric(df['매출액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['마진금액'] = pd.to_numeric(df['마진금액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

    # --- 동적 그룹핑 기준 설정 ---
    grouping_period = 'M' # 기본값은 월별
    if 'filter_type' in locals() and filter_type == '기간 지정':
        if 'start_date' in locals() and 'end_date' in locals():
            if (end_date - start_date).days <= 56:
                grouping_period = 'W' # 56일 (8주) 이하일 경우 주별로 변경

    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["종합 현황", "담당자/팀 분석", "문의 경로 분석", "영업 상태 분석"])

    # --- Tab 1: 종합 현황 ---
    with tab1:
        # KPI
        total_inquiries = len(df)
        successful_inquiries = df[df['상태'].isin(success_status)].shape[0] if '상태' in df.columns else 0
        confirmation_rate = (successful_inquiries / total_inquiries * 100) if total_inquiries > 0 else 0

        k1, k2, k3 = st.columns(3)
        k1.metric("조회 기간 총 문의", f"{total_inquiries}건")
        k2.metric("확정 및 완료", f"{successful_inquiries}건")
        k3.metric("확정율", f"{confirmation_rate:.1f}%")
        
        st.divider()

        # --- 동적 실적 추이 차트 ---
        if '문의 일자' in df.columns and not df.empty:
            # dropna를 제거하고, 원본 df의 복사본으로 작업하여 데이터 정합성 보장
            chart_df = df.copy()
            
            # 날짜가 유효한 행만 골라 인덱스로 설정
            chart_df_resample = chart_df.dropna(subset=['문의 일자']).set_index('문의 일자')

            # 그룹핑 및 집계
            if grouping_period == 'W':
                st.subheader("📊 실적 추이 (주별)")
                freq = 'W-MON'
                stats = chart_df_resample.resample(freq).agg(
                    전체=('기업명', 'count'),
                    성공=('상태', lambda x: x.isin(success_status).sum())
                )
                stats['기간_표시'] = stats.index.strftime('%Y-%m-%d')
                stats.reset_index(inplace=True)
            else: # 월별
                st.subheader("📊 실적 추이 (월별)")
                freq = 'MS'
                
                # 1. 실제 데이터 집계
                agg_stats = chart_df_resample.resample(freq).agg(
                    전체=('기업명', 'count'),
                    성공=('상태', lambda x: x.isin(success_status).sum())
                )

                # 2. 전체 기간에 대한 연속적인 월 생성 및 데이터 보정
                # 빈 데이터프레임이 아닐 경우에만 min/max 계산
                if not chart_df_resample.empty:
                    min_chart_date = chart_df_resample.index.min()
                    max_chart_date = chart_df_resample.index.max()
                    
                    # min/max 날짜가 유효한지 확인
                    if pd.notna(min_chart_date) and pd.notna(max_chart_date):
                        # resample과 동일한 월 시작일 기준으로 전체 범위 생성
                        all_months_index = pd.date_range(start=min_chart_date.to_period('M').to_timestamp(), end=max_chart_date, freq=freq)
                        
                        # 집계 데이터의 인덱스를 재설정하고 전체 월 범위와 합침 (없는 달은 0으로 채움)
                        stats = agg_stats.reindex(all_months_index, fill_value=0)
                    else:
                        stats = agg_stats # 날짜가 유효하지 않으면 원본 집계 사용
                else:
                    stats = agg_stats # 원본 데이터가 비었으면 빈 집계 사용
                
                stats.reset_index(inplace=True)
                stats.rename(columns={'index': '문의 일자'}, inplace=True)
                stats['기간_표시'] = stats['문의 일자'].dt.strftime('%Y년 %m월')
            
            # --- [1] 데이터 전처리 및 0값 제거 ---
            stats['확정율'] = (stats['성공'] / stats['전체'] * 100).round(1).where(stats['전체'] > 0, 0)

            # 텍스트 레이블 생성: 0이면 빈 문자열('') 반환
            stats['텍스트_표시_전체문의'] = stats['전체'].apply(lambda x: f"{x}" if x > 0 else '')
            stats['텍스트_표시_확정건수'] = stats['성공'].apply(lambda x: f"{x}" if x > 0 else '')
            stats['텍스트_표시_확정율'] = stats['확정율'].apply(lambda x: f"{x:.1f}%" if x > 0 else '')

            # --- [2] 텍스트 위치 계산 (겹침 최소화 로직) ---
            # 막대가 너무 낮으면(전체의 30% 미만) 글자를 위로 올림('outside'), 충분하면 안으로 넣음('inside')
            stats['성공_텍스트_위치'] = stats.apply(
                lambda row: 'outside' if row['성공'] < row['전체'] * 0.3 or row['성공'] < 5 else 'inside', axis=1
            )
            stats_inside = stats[stats['성공_텍스트_위치'] == 'inside']
            stats_outside = stats[stats['성공_텍스트_위치'] == 'outside']

            # --- [3] 스타일 설정 (핵심 수정) ---
            # 기존 3px (블러) -> 0px (선명한 테두리)로 변경! 글자가 아주 쨍하게 보입니다.
            sharp_halo = "1px 1px 0px white, -1px -1px 0px white, 1px -1px 0px white, -1px 1px 0px white"

            fig_rate = go.Figure()

            # Trace 1: 전체 문의 (배경 막대) - 연한 색상
            fig_rate.add_trace(go.Bar(
                x=stats['문의 일자'], y=stats['전체'], name='전체 문의',
                marker_color='#E3E7ED', marker_line_width=0,
                text=stats['텍스트_표시_전체문의'], textposition='outside',
                textfont=dict(color='#999999', size=10), # 회색으로 힘을 빼서 노이즈 감소
                hoverinfo='x+y'
            ))

            # Trace 2: 확정 건수 (메인 막대) - 진한 색상
            fig_rate.add_trace(go.Bar(
                x=stats['문의 일자'], y=stats['성공'], name='확정 건수',
                marker_color='#5B9BD5', marker_line_width=0, # 세련된 소프트 블루
                hoverinfo='x+y'
            ))

            # Trace 3: 확정 건수 텍스트 (막대 내부용) - 흰색 글씨 (bold 및 shadow 제거)
            if not stats_inside.empty:
                fig_rate.add_trace(go.Scatter(
                    x=stats_inside['문의 일자'], y=stats_inside['성공'] / 2, # 막대 중간에 위치
                    text=stats_inside['텍스트_표시_확정건수'],
                    mode='text', 
                    textfont=dict(color='white', size=11), # 선명한 흰색으로 롤백
                    hoverinfo='skip', showlegend=False
                ))

            # Trace 4: 확정 건수 텍스트 (막대 외부용) - 검은 글씨 (bold 및 shadow 제거)
            if not stats_outside.empty:
                fig_rate.add_trace(go.Scatter(
                    x=stats_outside['문의 일자'], y=stats_outside['성공'],
                    text=stats_outside['텍스트_표시_확정건수'],
                    mode='text', textposition="top center",
                    textfont=dict(color='black', size=11), # 선명한 검은색으로 롤백
                    hoverinfo='skip', showlegend=False
                ))

            # Trace 5: 확정율 (꺾은선) - 빨간색으로 변경
            fig_rate.add_trace(go.Scatter(
                x=stats['문의 일자'], y=stats['확정율'], name='확정율(%)',
                yaxis='y2',
                line=dict(color='#D9534F', width=3), # 빨간색 계열로 변경
                marker=dict(size=9, color='white', line=dict(color='#D9534F', width=2.5)), # 테두리도 빨간색으로
                mode='lines+markers+text',
                text=stats['텍스트_표시_확정율'],
                textposition="top center",
                textfont=dict(color='#D9534F', size=12, weight='bold', shadow=sharp_halo),
                hovertemplate='%{y:.1f}%<extra></extra>' 
            ))

            # Y축 최대값 설정 (여백 확보를 위해 1.5배)
            max_y_value = stats['전체'].max() if not stats.empty else 0

            # --- 레이아웃 최종 업데이트 ---
            fig_rate.update_layout(
                height=600,
                font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=14),
                
                # X축 디자인
                xaxis=dict(
                    type='date', tickformat='%y.%m', dtick='M1',
                    tickangle=0, # 45도 대신 0도로 깔끔하게 (공간 부족하면 자동으로 돌아감)
                    showgrid=False, showline=True, linecolor='lightgray'
                ),
                
                # Y1축 (왼쪽: 건수)
                yaxis=dict(
                    title='문의 건수',
                    range=[0, max_y_value * 1.5], # 위쪽 공간 넉넉하게 확보 (글자 짤림 방지)
                    showgrid=True, gridwidth=1, gridcolor='#F0F0F0', # 아주 연한 그리드
                    zeroline=False
                ),
                
                # Y2축 (오른쪽: 확정율)
                yaxis2=dict(
                    overlaying='y', side='right',
                    range=[-5, 115], # 0% ~ 100%가 중간에 오도록 조정
                    title='확정율(%)',
                    showgrid=False, zeroline=False
                ),
                
                barmode='overlay',
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                plot_bgcolor='white',
                margin=dict(t=80, b=40, l=40, r=40)
            )

            st.plotly_chart(fig_rate, use_container_width=True)



    # --- Tab 2: 담당자/팀 분석 ---
    with tab2:
        st.subheader("📈 담당자/팀별 실적 상세 분석")
        analysis_type = st.radio("분석 기준", ('담당자', '진행 팀'), horizontal=True, key='tab2_radio')
        
        if df.empty:
            st.warning("조회된 데이터가 없어 분석할 수 없습니다.")
        else:
            group_by_col = '담당자' if analysis_type == '담당자' else '진행 팀'
            
            # --- 데이터 집계 ---
            analysis_df = df.copy()
            if analysis_type == '담당자':
                analysis_df['담당자'] = analysis_df['담당자'].fillna('')
                analysis_df['담당자_수'] = analysis_df['담당자'].apply(lambda x: len(x.split(',')) if x and x.strip() else 1)
                if has_sales_data:
                    analysis_df['매출액'] = analysis_df['매출액'] / analysis_df['담당자_수']
                    analysis_df['마진금액'] = analysis_df['마진금액'] / analysis_df['담당자_수']
                analysis_df['담당자'] = analysis_df['담당자'].str.split(',')
                analysis_df = analysis_df.explode('담당자')
                analysis_df['담당자'] = analysis_df['담당자'].str.strip()

            agg_dict = { '문의건수': ('기업명', 'count'), '확정건수': ('상태', lambda x: x.isin(success_status).sum()) }
            if has_sales_data:
                agg_dict['매출액'] = ('매출액', 'sum')
                agg_dict['마진액'] = ('마진금액', 'sum')

            if analysis_type == '담당자':
                analysis_df = analysis_df[analysis_df['담당자'] != '']

            stats = analysis_df.groupby(group_by_col).agg(**agg_dict).reset_index()
            stats['확정율'] = (stats['확정건수'] / stats['문의건수'] * 100).round(1).where(stats['문의건수'] > 0, 0)
            if has_sales_data:
                stats['마진율'] = (stats['마진액'] / stats['매출액'] * 100).round(1).where(stats['매출액'] > 0, 0)

            # --- 필터 UI 및 차트 그리기 ---
            all_entities = sorted(stats[group_by_col].unique())
            
            with st.expander("담당자 선택", expanded=True):
                # 세션 상태 초기화
                for entity in all_entities:
                    if f"chk_{entity}" not in st.session_state:
                        st.session_state[f"chk_{entity}"] = True

                # 콜백 함수 정의
                def set_checkboxes(value, active_list=None):
                    for entity in all_entities:
                        if active_list:
                            st.session_state[f"chk_{entity}"] = entity in active_list
                        else:
                            st.session_state[f"chk_{entity}"] = value

                active_employees = ['안광열', '이서호', '조민채', '문서인', '변승민', '이채정']
                
                b_col1, b_col2, b_col3, _ = st.columns([1, 1, 1, 4])
                b_col1.button("전체 선택", on_click=set_checkboxes, args=(True,), use_container_width=True, key='btn_all')
                b_col2.button("전체 해제", on_click=set_checkboxes, args=(False,), use_container_width=True, key='btn_none')
                if analysis_type == '담당자':
                    b_col3.button("재직자 선택", on_click=set_checkboxes, args=(None, active_employees), use_container_width=True, key='btn_active')

                st.divider()

                selected_entities = []
                cols = st.columns(4)
                for i, entity in enumerate(all_entities):
                    if cols[i % 4].checkbox(entity, key=f"chk_{entity}"):
                        selected_entities.append(entity)
            
            if not selected_entities:
                st.warning("표시할 항목을 하나 이상 선택해주세요.")
            else:
                filtered_stats = stats[stats[group_by_col].isin(selected_entities)]
                if has_sales_data and not filtered_stats.empty:
                    stats_sorted_sales = filtered_stats.sort_values('매출액', ascending=False)
                    fig = px.bar(stats_sorted_sales, x=group_by_col, y=['매출액', '마진액'], title=f'{analysis_type}별 매출 및 마진', barmode='group', text_auto='.2s')
                    st.plotly_chart(fig, use_container_width=True)

                if not filtered_stats.empty:
                    # 확정율_표시 컬럼 생성
                    filtered_stats['확정율_표시'] = filtered_stats.apply(
                        lambda row: f"{row['확정율']}% (확정: {row['확정건수']}건 / 총: {row['문의건수']}건)", axis=1
                    )
                    # 가로 막대그래프를 위해 오름차순 정렬 (높은 값이 위로)
                    stats_sorted_rate = filtered_stats.sort_values('확정율', ascending=True)
                    
                    fig2 = px.bar(stats_sorted_rate, 
                                 x='확정율', 
                                 y=group_by_col, 
                                 title=f'{analysis_type}별 확정율', 
                                 color='확정율', 
                                 text='확정율_표시',
                                 orientation='h')
                    fig2.update_traces(textposition='outside')
                    # X축 범위 조정 (텍스트 잘림 방지)
                    fig2.update_xaxes(range=[0, stats_sorted_rate['확정율'].max() * 1.25])
                    st.plotly_chart(fig2, use_container_width=True)

    # --- Tab 3: 문의 경로 분석 ---
    with tab3:
        st.subheader("🚀 문의 경로별 효율 분석")
        if '문의경로' in df.columns and not df.empty:
            source_stats = df.groupby('문의경로').agg(
                문의건수=('기업명', 'count'),
                확정건수=('상태', lambda x: x.isin(success_status).sum())
            ).reset_index()
            source_stats['확정율'] = (source_stats['확정건수'] / source_stats['문의건수'] * 100).round(1)
            source_stats = source_stats.sort_values('문의건수', ascending=False)
            
            fig = px.bar(source_stats, x='문의경로', y='문의건수', title='문의 경로별 문의 건수', color='문의건수', text='문의건수')
            st.plotly_chart(fig, use_container_width=True)
            
            fig2 = px.bar(source_stats.sort_values('확정율', ascending=False), x='문의경로', y='확정율', title='문의 경로별 확정율', color='확정율', text='확정율')
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("데이터에 '문의경로' 열이 없거나 조회된 데이터가 없습니다.")

    # --- Tab 4: 영업 상태 분석 ---
    with tab4:
        st.subheader("📋 영업 기회 상태 분석")
        if '상태' in df.columns and not df.empty:
            status_counts = df['상태'].value_counts().reset_index()
            status_counts.columns = ['상태', '건수']
            
            fig = px.pie(status_counts, names='상태', values='건수', title='영업 기회 상태 분포', hole=0.3)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("데이터에 '상태' 열이 없거나 조회된 데이터가 없습니다.")