// 전역 변수로 원본 데이터 저장
let originalData = [];
const successStatus = ['확정', '진행 완료'];

// DOM이 로드되면 스크립트 실행
document.addEventListener('DOMContentLoaded', () => {
    // CSV 데이터 로드
    Papa.parse('data.csv', {
        download: true,
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        complete: (results) => {
            originalData = preprocessData(results.data);
            initializeApp();
        },
        error: (error) => {
            console.error("CSV 파일을 로드하거나 파싱하는 데 실패했습니다:", error);
            alert("데이터 파일(data.csv)을 로드하는 데 실패했습니다. 파일이 정확한 위치에 있는지 확인해주세요.");
        }
    });
});

/**
 * 데이터 전처리
 */
function preprocessData(data) {
    return data.filter(row => row['문의 일자']).map(row => {
        row.dateObject = new Date(row['문의 일자']);
        row['매출액'] = Number(String(row['매출액']).replace(/,/g, '')) || 0;
        row['마진금액'] = Number(String(row['마진금액']).replace(/,/g, '')) || 0;
        return row;
    });
}

/**
 * 앱 초기화
 */
function initializeApp() {
    if (originalData.length === 0) {
        alert("처리할 데이터가 없습니다.");
        return;
    }
    populateFilters();
    setupEventListeners();
    updateDashboard();
    document.getElementById('last-update').textContent = new Date().toLocaleString();
}

/**
 * 필터 옵션 채우기
 */
function populateFilters() {
    const teams = new Set();
    const managers = new Set();
    const years = new Set();
    
    originalData.forEach(row => {
        if (row['진행 팀']) teams.add(row['진행 팀']);
        if (row['담당자']) {
            row['담당자'].split(',').forEach(m => managers.add(m.trim()));
        }
        if (row.dateObject) {
            years.add(row.dateObject.getFullYear());
        }
    });

    const teamSelect = document.getElementById('team-select');
    const managerSelect = document.getElementById('manager-select');
    const yearSelect = document.getElementById('year-select');
    const monthYearSelect = document.getElementById('month-year-select');

    teamSelect.innerHTML = '<option value="전체">전체</option>' + [...teams].sort().map(t => `<option value="${t}">${t}</option>`).join('');
    managerSelect.innerHTML = '<option value="전체">전체</option>' + [...managers].sort().map(m => `<option value="${m}">${m}</option>`).join('');
    
    const sortedYears = [...years].sort((a, b) => b - a);
    yearSelect.innerHTML = sortedYears.map(y => `<option value="${y}">${y}</option>`).join('');
    monthYearSelect.innerHTML = sortedYears.map(y => `<option value="${y}">${y}</option>`).join('');
    
    updateMonthOptions(); // 초기 월 옵션 설정
}

/**
 * 연도 선택에 따라 월 필터 옵션 업데이트
 */
function updateMonthOptions() {
    const selectedYear = parseInt(document.getElementById('month-year-select').value);
    const months = new Set();
    originalData.forEach(row => {
        if (row.dateObject && row.dateObject.getFullYear() === selectedYear) {
            months.add(row.dateObject.getMonth() + 1);
        }
    });
    const monthSelect = document.getElementById('month-select');
    monthSelect.innerHTML = [...months].sort((a, b) => a - b).map(m => `<option value="${m}">${m}월</option>`).join('');
}


/**
 * 모든 필터에 대한 이벤트 리스너 설정
 */
function setupEventListeners() {
    // 기간 필터 유형 변경
    document.querySelectorAll('input[name="period"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            document.querySelectorAll('.date-filter-inputs').forEach(div => div.style.display = 'none');
            if (e.target.value !== 'all') {
                document.getElementById(`${e.target.value}-filter`).style.display = 'block';
            }
            updateDashboard();
        });
    });

    // 월 필터의 연도 변경 시 월 목록 업데이트
    document.getElementById('month-year-select').addEventListener('change', () => {
        updateMonthOptions();
        updateDashboard();
    });

    // 기타 모든 필터 변경
    const filterIds = ['start-date', 'end-date', 'year-select', 'month-select', 'team-select', 'manager-select'];
    filterIds.forEach(id => {
        document.getElementById(id).addEventListener('change', updateDashboard);
    });
    
    // 탭 클릭 이벤트
    document.querySelectorAll('.tab-link').forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.tab-link').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
        });
    });
}


/**
 * 대시보드 업데이트 (필터 변경 시 호출)
 */
function updateDashboard() {
    const filters = getAppliedFilters();
    const filteredData = applyFilters(filters);
    updateKPIs(filteredData);
    updateCharts(filteredData);
}

/**
 * 현재 활성화된 필터 값들을 객체로 반환
 */
function getAppliedFilters() {
    const periodType = document.querySelector('input[name="period"]:checked').value;
    return {
        periodType,
        startDate: document.getElementById('start-date').value,
        endDate: document.getElementById('end-date').value,
        year: parseInt(document.getElementById('year-select').value),
        monthYear: parseInt(document.getElementById('month-year-select').value),
        month: parseInt(document.getElementById('month-select').value),
        team: document.getElementById('team-select').value,
        manager: document.getElementById('manager-select').value,
    };
}

/**
 * 원본 데이터에 필터를 적용하여 결과를 반환
 */
function applyFilters(filters) {
    return originalData.filter(row => {
        // 날짜 필터
        if (!row.dateObject) return false;
        const date = row.dateObject;
        if (filters.periodType === 'range' && filters.startDate && filters.endDate) {
            if (date < new Date(filters.startDate) || date > new Date(filters.endDate)) return false;
        } else if (filters.periodType === 'year') {
            if (date.getFullYear() !== filters.year) return false;
        } else if (filters.periodType === 'month') {
            if (date.getFullYear() !== filters.monthYear || (date.getMonth() + 1) !== filters.month) return false;
        }
        
        // 팀 필터
        if (filters.team !== '전체' && row['진행 팀'] !== filters.team) return false;

        // 담당자 필터
        if (filters.manager !== '전체' && (!row['담당자'] || !row['담당자'].split(',').map(m=>m.trim()).includes(filters.manager))) return false;
        
        return true;
    });
}

/**
 * KPI 카드 업데이트
 */
function updateKPIs(data) {
    const totalInquiries = data.length;
    const successfulInquiries = data.filter(row => successStatus.includes(row['상태'])).length;
    const confirmationRate = totalInquiries > 0 ? (successfulInquiries / totalInquiries * 100) : 0;

    document.getElementById('kpi-total-inquiries').textContent = `${totalInquiries}건`;
    document.getElementById('kpi-successful-inquiries').textContent = `${successfulInquiries}건`;
    document.getElementById('kpi-confirmation-rate').textContent = `${confirmationRate.toFixed(1)}%`;
}

/**
 * 모든 차트 업데이트
 */
function updateCharts(data) {
    // 현재 활성화된 탭을 확인하고 해당 차트만 그림
    const activeTab = document.querySelector('.tab-link.active');
    const tabId = activeTab ? activeTab.getAttribute('onclick').match(/'([^']*)'/)[1] : 'tab1';

    switch(tabId) {
        case 'tab1':
            createTimeSeriesChart(data);
            break;
        case 'tab2':
            createManagerTeamChart(data, '담당자'); // 담당자 기준으로 차트 생성
            break;
        case 'tab3':
            createSourceAnalysisChart(data);
            break;
        case 'tab4':
            createStatusPieChart(data);
            break;
    }
}

/**
 * 탭 전환 로직
 */
function openTab(evt, tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.style.display = 'none');
    
    const oldActiveTab = document.querySelector('.tab-link.active');
    if(oldActiveTab) {
        const oldTabContentId = oldActiveTab.getAttribute('onclick').match(/'([^']*)'/)[1];
        const chartDiv = document.getElementById(oldTabContentId).querySelector('.chart-container');
        if(chartDiv) Plotly.purge(chartDiv.id);
    }
    
    document.querySelectorAll('.tab-link').forEach(link => link.classList.remove('active'));

    document.getElementById(tabName).style.display = 'block';
    evt.currentTarget.classList.add('active');
    
    updateDashboard(); 
}

// --- 차트 생성 헬퍼 함수 ---

/**
 * 데이터를 시간 단위(주/월)로 그룹화하는 함수
 */
function groupByTime(data, period = 'M') {
    const grouped = {};
    data.forEach(row => {
        if (!row.dateObject) return;
        let key;
        const date = row.dateObject;
        if (period === 'W') {
            const day = date.getDay();
            const diff = date.getDate() - day + (day === 0 ? -6 : 1);
            const monday = new Date(new Date(date).setDate(diff));
            key = monday.toISOString().split('T')[0];
        } else {
            key = new Date(date.getFullYear(), date.getMonth(), 1).toISOString().split('T')[0];
        }
        if (!grouped[key]) grouped[key] = { 전체: 0, 성공: 0 };
        grouped[key].전체 += 1;
        if (successStatus.includes(row['상태'])) grouped[key].성공 += 1;
    });
    return Object.entries(grouped).map(([date, values]) => ({ date, ...values }))
           .sort((a,b) => new Date(a.date) - new Date(b.date));
}


// --- 차트 생성 함수들 ---

/**
 * 종합 현황: 실적 추이 차트
 */
function createTimeSeriesChart(data) {
    const aggregatedData = groupByTime(data, 'M');
    if (aggregatedData.length === 0) {
        Plotly.newPlot('time-series-chart', [], {title: '표시할 데이터가 없습니다.'});
        return;
    }
    // ... (이전과 동일한 차트 로직)
    const dates = aggregatedData.map(d => d.date);
    const total = aggregatedData.map(d => d.전체);
    const success = aggregatedData.map(d => d.성공);
    const rates = aggregatedData.map(d => d.전체 > 0 ? (d.성공 / d.전체 * 100) : 0);

    const trace1 = { x: dates, y: total, name: '전체 문의', type: 'bar', marker: { color: '#E3E7ED' }, hoverinfo: 'x+y' };
    const trace2 = { x: dates, y: success, name: '확정 건수', type: 'bar', marker: { color: '#5B9BD5' }, hoverinfo: 'x+y' };
    const trace3 = { x: dates, y: rates, name: '확정율(%)', type: 'scatter', mode: 'lines+markers', yaxis: 'y2', line: { color: '#D9534F' }, marker: { color: 'white', size: 8, line: { color: '#D9534F', width: 2 } }, hovertemplate: '%{y:.1f}%<extra></extra>' };

    const layout = { height: 600, font: { family: "Malgun Gothic, Apple SD Gothic Neo, sans-serif", size: 14 }, barmode: 'overlay', legend: { orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "right", x: 1 }, xaxis: { type: 'date', showgrid: false }, yaxis: { title: '문의 건수', showgrid: true, gridcolor: '#F0F0F0' }, yaxis2: { title: '확정율(%)', overlaying: 'y', side: 'right', range: [0, 100], showgrid: false }, plot_bgcolor: 'white', margin: { t: 80, b: 40, l: 60, r: 60 } };
    Plotly.newPlot('time-series-chart', [trace1, trace2, trace3], layout, {responsive: true});
}

/**
 * 담당자/팀별 실적 분석 차트
 */
function createManagerTeamChart(data, groupBy) {
    const stats = {};
    data.forEach(row => {
        const keys = row[groupBy] ? String(row[groupBy]).split(',').map(k => k.trim()) : ['(미지정)'];
        keys.forEach(key => {
            if (!key) return;
            if (!stats[key]) stats[key] = { 문의건수: 0, 확정건수: 0 };
            stats[key].문의건수 += 1 / keys.length; // 공동 담당 시 1/n으로 기여도 분배
            if (successStatus.includes(row['상태'])) {
                stats[key].확정건수 += 1 / keys.length;
            }
        });
    });

    const sortedData = Object.entries(stats).map(([key, value]) => ({
        key,
        ...value,
        확정율: value.문의건수 > 0 ? (value.확정건수 / value.문의건수 * 100) : 0
    })).sort((a,b) => b.문의건수 - a.문의건수);

    const trace1 = {
        x: sortedData.map(d => d.key),
        y: sortedData.map(d => d.문의건수),
        name: '총 문의 건수',
        type: 'bar'
    };
    const trace2 = {
        x: sortedData.map(d => d.key),
        y: sortedData.map(d => d.확정건수),
        name: '확정 건수',
        type: 'bar'
    };

    const layout = {
        title: `${groupBy}별 실적 분석`,
        barmode: 'group'
    };
    Plotly.newPlot('manager-team-chart', [trace1, trace2], layout, {responsive: true});
}

/**
 * 문의 경로 분석 차트
 */
function createSourceAnalysisChart(data) {
    const stats = {};
    data.forEach(row => {
        const key = row['문의경로'] || '(미지정)';
        if (!stats[key]) stats[key] = { 문의건수: 0 };
        stats[key].문의건수 += 1;
    });
    
    const sortedData = Object.entries(stats).sort((a,b) => b[1].문의건수 - a[1].문의건수);

    const trace = {
        x: sortedData.map(d => d[0]),
        y: sortedData.map(d => d[1].문의건수),
        type: 'bar',
        text: sortedData.map(d => d[1].문의건수),
        textposition: 'auto'
    };

    Plotly.newPlot('source-analysis-chart', [trace], {title: '문의 경로별 문의 건수'}, {responsive: true});
}

/**
 * 영업 상태 분석 파이 차트
 */
function createStatusPieChart(data) {
    const stats = {};
    data.forEach(row => {
        const key = row['상태'] || '(미지정)';
        if (!stats[key]) stats[key] = 0;
        stats[key] += 1;
    });

    const trace = {
        labels: Object.keys(stats),
        values: Object.values(stats),
        type: 'pie',
        hole: 0.3,
        textinfo: 'percent+label'
    };

    Plotly.newPlot('status-pie-chart', [trace], {title: '영업 기회 상태 분포'}, {responsive: true});
}
