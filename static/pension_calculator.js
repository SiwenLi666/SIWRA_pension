// Pension Calculator UI Logic
// Loads parameters from calculation_parameters.json, renders UI, syncs with chat context, and performs real-time calculations

let calculationParameters = {};
let currentAgreement = null;
let currentScenario = null;
let calculatorState = {};

async function loadCalculationParameters() {
    try {
        const response = await fetch('/calculation_parameters.json');
        if (!response.ok) {
            throw new Error('Kunde inte ladda pensionsparametrar. Kontrollera serverns konfiguration.');
        }
        calculationParameters = await response.json();
    } catch (error) {
        calculationParameters = {};
        alert('Fel vid inläsning av pensionsparametrar: ' + error.message);
    }
}

function renderAgreementSelector() {
    const agreementSelect = document.getElementById('agreement-select');
    agreementSelect.innerHTML = '';
    Object.keys(calculationParameters).forEach(agreement => {
        const option = document.createElement('option');
        option.value = agreement;
        option.textContent = agreement;
        agreementSelect.appendChild(option);
    });
}

function renderScenarioSelector() {
    const scenarioSelect = document.getElementById('scenario-select');
    scenarioSelect.innerHTML = '';
    if (!currentAgreement) return;
    const scenarios = calculationParameters[currentAgreement].scenarios;
    Object.keys(scenarios).forEach(scenario => {
        const option = document.createElement('option');
        option.value = scenario;
        option.textContent = scenario;
        scenarioSelect.appendChild(option);
    });
}

function renderParameterInputs() {
    const paramContainer = document.getElementById('parameter-inputs');
    paramContainer.innerHTML = '';
    if (!currentAgreement || !currentScenario) return;
    const scenarioObj = calculationParameters[currentAgreement].scenarios[currentScenario];
    // Dynamically show all scenario parameters and core user inputs
    const scenarioFields = Object.keys(scenarioObj);
    // Only show three main fields: Ålder, Lön, Pensionsålder
    const scenarioType = scenarioObj.type;
    let mainFields = [
        { key: 'age', label: 'Ålder', default: 40 },
        { key: 'salary', label: 'Lön (kr/mån)', default: 50000 },
        { key: 'retirement_age', label: 'Pensionsålder', default: scenarioObj.default_retirement_age || 65 }
    ];
    let isAvd2 = (currentAgreement === 'PA16' && currentScenario === 'Avd2' && scenarioType === 'förmånsbestämd');
    if (isAvd2 && Array.isArray(scenarioObj.defined_benefit_levels)) {
        // Show both start year and years of service, dual-bound
        mainFields.push({ key: 'start_work_year', label: 'Startår (år du började arbeta)', default: new Date().getFullYear() - 10 });
        mainFields.push({ key: 'years_of_service', label: 'Tjänsteår', default: 10 });
        mainFields.push({ key: 'defined_benefit_levels', label: 'Förmånsnivåer', default: scenarioObj.defined_benefit_levels });
    }
    // Custom rendering for Avd2 dual-bound fields
    if (isAvd2 && Array.isArray(scenarioObj.defined_benefit_levels)) {
        // Remove any previous custom fields
        paramContainer.innerHTML = '';
        // Age, Salary, Retirement Age
        ['age','salary','retirement_age'].forEach(key => {
            const div = document.createElement('div');
            div.className = 'mb-2';
            const label = document.createElement('label');
            label.textContent = key === 'age' ? 'Ålder' : key === 'salary' ? 'Lön (kr/mån)' : 'Pensionsålder';
            label.setAttribute('for', `input-${key}`);
            const input = document.createElement('input');
            input.type = 'number';
            input.className = 'form-control';
            input.id = `input-${key}`;
            input.value = calculatorState[key] !== undefined ? calculatorState[key] : (key==='age'?40:key==='salary'?50000:scenarioObj.default_retirement_age||65);
            input.addEventListener('input', () => {
                calculatorState[key] = parseFloat(input.value);
                performCalculation();
                syncCalculatorToChat();
            });
            div.appendChild(label);
            div.appendChild(input);
            paramContainer.appendChild(div);
        });
        // Dual-bound fields
        const dualDiv = document.createElement('div');
        dualDiv.className = 'row mb-2';
        // Startår
        const startCol = document.createElement('div');
        startCol.className = 'col-6';
        const startLabel = document.createElement('label');
        startLabel.textContent = 'Startår (år du började arbeta)';
        startLabel.setAttribute('for','input-start_work_year');
        const startInput = document.createElement('input');
        startInput.type = 'number';
        startInput.className = 'form-control';
        startInput.id = 'input-start_work_year';
        startInput.value = calculatorState['start_work_year'] !== undefined ? calculatorState['start_work_year'] : (new Date().getFullYear() - 10);
        startCol.appendChild(startLabel);
        startCol.appendChild(startInput);
        dualDiv.appendChild(startCol);
        // Tjänsteår
        const yearsCol = document.createElement('div');
        yearsCol.className = 'col-6';
        const yearsLabel = document.createElement('label');
        yearsLabel.textContent = 'Tjänsteår';
        yearsLabel.setAttribute('for','input-years_of_service');
        const yearsInput = document.createElement('input');
        yearsInput.type = 'number';
        yearsInput.className = 'form-control';
        yearsInput.id = 'input-years_of_service';
        yearsInput.value = calculatorState['years_of_service'] !== undefined ? calculatorState['years_of_service'] : 10;
        yearsCol.appendChild(yearsLabel);
        yearsCol.appendChild(yearsInput);
        dualDiv.appendChild(yearsCol);
        paramContainer.appendChild(dualDiv);
        // Dual binding logic
        // When start year changes, update years of service
        startInput.addEventListener('input', () => {
            const currentYear = new Date().getFullYear();
            const retirementAge = Number(document.getElementById('input-retirement_age').value);
            const age = Number(document.getElementById('input-age').value);
            const retirementYear = currentYear + (retirementAge - age);
            const startYear = parseInt(startInput.value);
            const yearsOfService = Math.max(0, retirementYear - startYear);
            yearsInput.value = yearsOfService;
            calculatorState['start_work_year'] = startYear;
            calculatorState['years_of_service'] = yearsOfService;
            performCalculation();
            syncCalculatorToChat();
        });
        // When years of service changes, update start year
        yearsInput.addEventListener('input', () => {
            const currentYear = new Date().getFullYear();
            const retirementAge = Number(document.getElementById('input-retirement_age').value);
            const age = Number(document.getElementById('input-age').value);
            const retirementYear = currentYear + (retirementAge - age);
            const yearsOfService = parseInt(yearsInput.value);
            const startYear = retirementYear - yearsOfService;
            startInput.value = startYear;
            calculatorState['start_work_year'] = startYear;
            calculatorState['years_of_service'] = yearsOfService;
            performCalculation();
            syncCalculatorToChat();
        });
        // Show defined benefit levels
        const levelsDiv = document.createElement('div');
        levelsDiv.className = 'mt-2';
        const levelsLabel = document.createElement('label');
        levelsLabel.textContent = 'Förmånsnivåer';
        levelsDiv.appendChild(levelsLabel);
        (scenarioObj.defined_benefit_levels || []).forEach((level, idx) => {
            const row = document.createElement('div');
            row.className = 'row mb-1';
            const col1 = document.createElement('div');
            col1.className = 'col-6';
            col1.textContent = `Tjänsteår: ${level.years}`;
            const col2 = document.createElement('div');
            col2.className = 'col-6';
            col2.textContent = `Förmån: ${(level.percent * 100).toFixed(2)}%`;
            row.appendChild(col1);
            row.appendChild(col2);
            levelsDiv.appendChild(row);
        });
        paramContainer.appendChild(levelsDiv);
        return;
    }
    mainFields.forEach(field => {
        const div = document.createElement('div');
        div.className = 'mb-2';
        const label = document.createElement('label');
        label.textContent = field.label;
        label.setAttribute('for', `input-${field.key}`);
        let input;
        if (field.key === 'defined_benefit_levels' && isAvd2) {
            // Render each benefit level as a row
            input = document.createElement('div');
            (field.default || []).forEach((level, idx) => {
                const row = document.createElement('div');
                row.className = 'row mb-1';
                const col1 = document.createElement('div');
                col1.className = 'col-6';
                col1.textContent = `Tjänsteår: ${level.years}`;
                const col2 = document.createElement('div');
                col2.className = 'col-6';
                col2.textContent = `Förmån: ${(level.percent * 100).toFixed(2)}%`;
                row.appendChild(col1);
                row.appendChild(col2);
                input.appendChild(row);
            });
        } else {
            input = document.createElement('input');
            input.type = 'number';
            input.className = 'form-control';
            input.id = `input-${field.key}`;
            input.value = calculatorState[field.key] !== undefined ? calculatorState[field.key] : field.default;
            input.addEventListener('input', () => {
                calculatorState[field.key] = parseFloat(input.value);
                performCalculation();
                syncCalculatorToChat();
            });
        }
        div.appendChild(label);
        div.appendChild(input);
        paramContainer.appendChild(div);
    });

    // Advanced toggle button
    let advancedVisible = false;
    let advancedBtn = document.getElementById('advanced-toggle-btn');
    if (!advancedBtn) {
        advancedBtn = document.createElement('button');
        advancedBtn.id = 'advanced-toggle-btn';
        advancedBtn.type = 'button';
        advancedBtn.className = 'btn btn-outline-secondary mb-3';
        advancedBtn.innerHTML = 'Visa avancerade inställningar';
        advancedBtn.onclick = function() {
            advancedVisible = !advancedVisible;
            document.getElementById('advanced-params').style.maxHeight = advancedVisible ? '1000px' : '0';
            document.getElementById('advanced-params').style.opacity = advancedVisible ? '1' : '0';
            advancedBtn.innerHTML = advancedVisible ? 'Dölj avancerade inställningar' : 'Visa avancerade inställningar';
        };
    }
    paramContainer.appendChild(advancedBtn);

    // Advanced fields (hidden by default): all scenario parameters except the three main ones
    let advDiv = document.getElementById('advanced-params');
    if (!advDiv) {
        advDiv = document.createElement('div');
        advDiv.id = 'advanced-params';
        advDiv.style.transition = 'max-height 0.45s cubic-bezier(.4,0,.2,1), opacity 0.35s';
        advDiv.style.overflow = 'hidden';
        advDiv.style.maxHeight = '0';
        advDiv.style.opacity = '0';
    } else {
        advDiv.innerHTML = '';
    }
    // Add scenario fields (with Swedish-friendly labels) to advanced
    const fieldLabelMap = {
        'type': 'Pensionstyp',
        'contribution_rate_below_cap': 'Premie under tak (%)',
        'contribution_rate_above_cap': 'Premie över tak (%)',
        'income_cap_base_amount': 'Inkomsttak (basbelopp)',
        'income_base_amount': 'Basbelopp (kr)',
        'admin_fee_percentage': 'Administrationsavgift (%)',
        'default_return_rate': 'Standard tillväxt (%)',
        'default_retirement_age': 'Standard pensionsålder',
        'defined_benefit_levels': 'Förmånsnivåer',
        'itpk_contribution_rate': 'ITPK-premie (%)',
        'family_pension_threshold': 'Familjepension (gräns)'
    };
    let scenarioRow = null;
    let scenarioCount = 0;
    scenarioFields.forEach(field => {
        if (mainFields.find(f => f.key === field)) return;
        if (scenarioObj[field] === undefined) return;
        if (scenarioCount % 3 === 0) {
            scenarioRow = document.createElement('div');
            scenarioRow.className = 'row mb-2';
            advDiv.appendChild(scenarioRow);
        }
        const col = document.createElement('div');
        col.className = 'col-md-4';
        const label = document.createElement('label');
        label.textContent = fieldLabelMap[field] || field;
        label.setAttribute('for', `input-${field}`);
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control';
        input.id = `input-${field}`;
        input.value = scenarioObj[field];
        input.readOnly = true;
        col.appendChild(label);
        col.appendChild(input);
        scenarioRow.appendChild(col);
        scenarioCount++;
    });
    paramContainer.appendChild(advDiv);
}

function performCalculation() {
    if (!currentAgreement || !currentScenario) return;
    const scenarioObj = calculationParameters[currentAgreement].scenarios[currentScenario];
    // Ensure resultTop exists for all scenarios
    let resultTop = document.getElementById('result-top');
    if (!resultTop) {
        resultTop = document.createElement('div');
        resultTop.id = 'result-top';
        const form = document.getElementById('calculator-form');
        form.insertBefore(resultTop, form.firstChild);
    }
    // User inputs
    const age = Number(calculatorState['age'] ?? 40);
    const salary = Number(calculatorState['salary'] ?? 50000);
    const retirementAge = Number(calculatorState['retirement_age'] ?? scenarioObj.default_retirement_age ?? 65);
    const growth = Number(calculatorState['growth'] ?? scenarioObj.default_return_rate ?? 0.019);
    const salaryExchange = Number(calculatorState['salary_exchange'] ?? 0);
    const salaryExchangePremium = Number(calculatorState['salary_exchange_premium'] ?? 0);
    let yearsToPension = retirementAge - age;

    // Parameters from scenario
    const rateBelow = scenarioObj.contribution_rate_below_cap || 0;
    const rateAbove = scenarioObj.contribution_rate_above_cap || 0;
    const incomeCap = scenarioObj.income_cap_base_amount || 0;
    const baseAmount = scenarioObj.income_base_amount || 0;

    // Förmånsbestämd branch
    if (scenarioObj.type === 'förmånsbestämd' && Array.isArray(scenarioObj.defined_benefit_levels) && scenarioObj.defined_benefit_levels.length > 0) {
        // Always calculate years_of_service from start_work_year and retirement year
        const currentYear = new Date().getFullYear();
        const retirementAge = Number(calculatorState['retirement_age'] ?? scenarioObj.default_retirement_age ?? 65);
        const age = Number(calculatorState['age'] ?? 40);
        const retirementYear = currentYear + (retirementAge - age);
        const startWorkYear = Number(calculatorState['start_work_year'] ?? (currentYear - 10));
        const yearsOfService = Math.max(0, retirementYear - startWorkYear);
        calculatorState['years_of_service'] = yearsOfService;
        // Find correct benefit percent based on years of service (use highest matching bracket)
        let benefitPercent = 0;
        scenarioObj.defined_benefit_levels.forEach((level, idx) => {
            let yearsCond = level.years;
            let percent = level.percent;
            if ((yearsCond === '<=30' && yearsOfService <= 30) || (yearsCond === '>30' && yearsOfService > 30)) {
                benefitPercent = percent;
            }
        });
        // Annual pension estimate
        let annualPension = salary * 12 * benefitPercent;
        let monthlyPension = annualPension / 12;
        // Ensure resultTop exists
        let resultTop = document.getElementById('result-top');
        if (!resultTop) {
            resultTop = document.createElement('div');
            resultTop.id = 'result-top';
            const form = document.getElementById('calculator-form');
            form.insertBefore(resultTop, form.firstChild);
        }
        resultTop.innerHTML = `
          <div class="result-summary-card" style="display: flex; flex-wrap: wrap; justify-content: center; align-items: stretch; gap: 2.5em; background: #fff; border-radius: 18px; box-shadow: 0 4px 24px rgba(33,150,243,0.09); padding: 28px 18px 18px 18px; margin-bottom: 18px;">
            <div class="result-block" style="flex:1 1 170px; min-width:150px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#43a047;">${isNaN(annualPension) ? '-' : annualPension.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
              <div style="color:#43a047; font-size:1.15em; margin-bottom:2px;">kr/år</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Årlig pension</div>
            </div>
            <div class="result-block" style="flex:1 1 170px; min-width:150px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#1976d2;">${isNaN(monthlyPension) ? '-' : monthlyPension.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
              <div style="color:#1976d2; font-size:1.15em; margin-bottom:2px;">kr/mån</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Månatlig pension</div>
            </div>
            <div class="result-block" style="flex:1 1 120px; min-width:110px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#b28900;">${isNaN(yearsOfService) ? '-' : yearsOfService}</div>
              <div style="color:#b28900; font-size:1.15em; margin-bottom:2px;">år</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Tjänsteår</div>
            </div>
          </div>
        `;
        return;
    }

    // Calculations
    const annualSalary = salary * 12;
    const cap = incomeCap * baseAmount * 12;
    const belowCap = Math.min(annualSalary, cap);
    const aboveCap = Math.max(annualSalary - cap, 0);
    const belowCapContribution = belowCap * rateBelow;
    const aboveCapContribution = aboveCap * rateAbove;
    const annualContribution = belowCapContribution + aboveCapContribution + (salaryExchange * 12 * (salaryExchangePremium / 100));
    const monthlyContribution = annualContribution / 12;

    // Growth simulation
    let total = 0;
    let yearlyResults = [];
    for (let year = 1; year <= yearsToPension; year++) {
        total = (total + annualContribution) * (1 + growth);
        yearlyResults.push({
            year,
            value: total
        });
    }
    // Final results
    const monthlyPension = yearsToPension > 0 ? total / (yearsToPension * 12) : 0;

    // Render results in a single, clear, horizontally-aligned card
    resultTop.innerHTML = `
      <div class=\"result-summary-card\" style=\"display: flex; flex-wrap: wrap; justify-content: center; align-items: stretch; gap: 2.5em; background: #fff; border-radius: 18px; box-shadow: 0 4px 24px rgba(33,150,243,0.09); padding: 28px 18px 18px 18px; margin-bottom: 18px;\">
        <div class=\"result-block\" style=\"flex:1 1 170px; min-width:150px; text-align:center;\">
          <div style=\"font-size:2.1em; font-weight:700; color:#43a047;\">${isNaN(annualContribution) ? '-' : annualContribution.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style=\"color:#43a047; font-size:1.15em; margin-bottom:2px;\">kr/år</div>
          <div style=\"font-size:1.07em; color:#222; margin-bottom:2px;\">Årlig avsättning</div>
        </div>
        <div class=\"result-block\" style=\"flex:1 1 170px; min-width:150px; text-align:center;\">
          <div style=\"font-size:2.1em; font-weight:700; color:#1976d2;\">${isNaN(monthlyContribution) ? '-' : monthlyContribution.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style=\"color:#1976d2; font-size:1.15em; margin-bottom:2px;\">kr/mån</div>
          <div style=\"font-size:1.07em; color:#222; margin-bottom:2px;\">Månatlig avsättning</div>
        </div>
        <div class=\"result-block\" style=\"flex:1 1 120px; min-width:110px; text-align:center;\">
          <div style=\"font-size:2.1em; font-weight:700; color:#b28900;\">${isNaN(yearsToPension) ? '-' : yearsToPension}</div>
          <div style=\"color:#b28900; font-size:1.15em; margin-bottom:2px;\">år</div>
          <div style=\"font-size:1.07em; color:#222; margin-bottom:2px;\">År till pension</div>
        </div>
        <div class=\"result-block\" style=\"flex:1 1 180px; min-width:150px; text-align:center;\">
          <div style=\"font-size:2.1em; font-weight:700; color:#0d47a1;\">${isNaN(total) ? '-' : total.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style=\"color:#0d47a1; font-size:1.15em; margin-bottom:2px;\">kr</div>
          <div style=\"font-size:1.07em; color:#222; margin-bottom:2px;\">Totalt kapital</div>
        </div>
        <div class=\"result-block\" style=\"flex:1 1 180px; min-width:150px; text-align:center;\">
          <div style=\"font-size:2.1em; font-weight:700; color:#b28900;\">${isNaN(monthlyPension) ? '-' : monthlyPension.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style=\"color:#b28900; font-size:1.15em; margin-bottom:2px;\">kr/mån</div>
          <div style=\"font-size:1.07em; color:#222; margin-bottom:2px;\">🧓 Månatlig pension</div>
        </div>
      </div>
      ${document.getElementById('advanced-params') && document.getElementById('advanced-params').style.maxHeight !== '0px' ?
        `<div class='row mt-3'><div class='col-12'><div class='alert alert-secondary' style='font-size:1.08em;'><strong>Årlig utveckling:</strong><div id='calc-yearly-breakdown' style='font-size:0.95em; max-height:180px; overflow-y:auto;'></div></div></div></div>` : ''}
    `;
    // Show yearly breakdown only if advanced params are open
    if (document.getElementById('advanced-params') && document.getElementById('advanced-params').style.maxHeight !== '0px') {
      const yearlyDiv = document.getElementById('calc-yearly-breakdown');
      if (yearlyDiv) yearlyDiv.innerHTML = yearlyResults.map(r => `<span style='color:#1976d2;'>År ${r.year}:</span> <span style='color:#388e3c;'>${r.value.toLocaleString('sv-SE', {maximumFractionDigits:2})} kr</span>`).join('<br>');
    }

}


function syncCalculatorToChat() {
    // MVP: Optionally send a message to chat or update context
    // For now, just log (integration with backend/chat to be implemented)
    // Example: window.postMessage({type: 'calculator_update', data: calculatorState}, '*');
}

function syncChatToCalculator(params) {
    // Called when chat detects calculation intent and extracts parameters
    if (params.salary) calculatorState.salary = params.salary;
    if (params.age) calculatorState.age = params.age;
    renderParameterInputs();
    performCalculation();
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadCalculationParameters();
    renderAgreementSelector();
    document.getElementById('agreement-select').addEventListener('change', e => {
        currentAgreement = e.target.value;
        renderScenarioSelector();
        currentScenario = document.getElementById('scenario-select').value;
        renderParameterInputs();
        performCalculation();
    });
    document.getElementById('scenario-select').addEventListener('change', e => {
        currentScenario = e.target.value;
        renderParameterInputs();
        performCalculation();
    });
    // Set defaults
    currentAgreement = document.getElementById('agreement-select').value;
    renderScenarioSelector();
    currentScenario = document.getElementById('scenario-select').value;
    renderParameterInputs();
    performCalculation();
});
