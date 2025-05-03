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
            const defaultValue = calculatorState[key] !== undefined
                ? calculatorState[key]
                : (key === 'age' ? 40 : key === 'salary' ? 50000 : scenarioObj.default_retirement_age || 65);
            input.value = defaultValue;
        
            // 🔧 THIS is the key fix: actually update calculatorState!
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

        // 🔄 When age changes, update years_of_service
        document.getElementById('input-age').addEventListener('input', () => {
            const currentYear = new Date().getFullYear();
            const retirementAge = parseFloat(document.getElementById('input-retirement_age').value);
            const age = parseFloat(document.getElementById('input-age').value);
            const startYear = parseFloat(document.getElementById('input-start_work_year').value);
            const retirementYear = currentYear + (retirementAge - age);
            const yearsOfService = Math.max(0, retirementYear - startYear);
            document.getElementById('input-years_of_service').value = yearsOfService;
            calculatorState['age'] = age;
            calculatorState['years_of_service'] = yearsOfService;
            performCalculation();
            syncCalculatorToChat();
        });

        // 🔄 When retirement_age changes, update years_of_service
        document.getElementById('input-retirement_age').addEventListener('input', () => {
            const currentYear = new Date().getFullYear();
            const retirementAge = parseFloat(document.getElementById('input-retirement_age').value);
            const age = parseFloat(document.getElementById('input-age').value);
            const startYear = parseFloat(document.getElementById('input-start_work_year').value);
            const retirementYear = currentYear + (retirementAge - age);
            const yearsOfService = Math.max(0, retirementYear - startYear);
            document.getElementById('input-years_of_service').value = yearsOfService;
            calculatorState['retirement_age'] = retirementAge;
            calculatorState['years_of_service'] = yearsOfService;
            performCalculation();
            syncCalculatorToChat();
        });

        // 🔄 When salary changes, update calculation directly
        document.getElementById('input-salary').addEventListener('input', () => {
            const salary = parseFloat(document.getElementById('input-salary').value);
            calculatorState['salary'] = salary;
            performCalculation();
            syncCalculatorToChat();
        });

        // ✅ Force-update calculatorState so performCalculation uses correct values on scenario switch
        calculatorState['age'] = parseFloat(document.getElementById('input-age').value);
        calculatorState['salary'] = parseFloat(document.getElementById('input-salary').value);
        calculatorState['retirement_age'] = parseFloat(document.getElementById('input-retirement_age').value);
        calculatorState['start_work_year'] = parseFloat(document.getElementById('input-start_work_year').value);
        calculatorState['years_of_service'] = parseFloat(document.getElementById('input-years_of_service').value);

        performCalculation();

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
    // RESET BUTTON
    const resetBtn = document.createElement('button');
    resetBtn.id = 'reset-params-btn';
    resetBtn.type = 'button';
    resetBtn.className = 'btn btn-outline-danger mb-3 ms-3';
    resetBtn.innerHTML = 'Återställ till standardvärden';
    resetBtn.onclick = function () {
        const scenarioDefaults = calculationParameters[currentAgreement].scenarios[currentScenario];
        calculatorState = {}; // Clear current values
        Object.keys(scenarioDefaults).forEach(key => {
            const inputEl = document.getElementById(`input-${key}`);
            if (!inputEl) return;

            // Convert % fields back to decimal in state and show 100x in UI
            if (inputEl.type === 'text' && inputEl.value && inputEl.labels?.[0]?.textContent?.includes('%')) {
                const raw = parseFloat(scenarioDefaults[key]);
                if (!isNaN(raw)) {
                    inputEl.value = (raw * 100).toFixed(2);
                    calculatorState[key] = raw;
                }
            } else {
                inputEl.value = scenarioDefaults[key];
                calculatorState[key] = scenarioDefaults[key];
            }
        });

        renderParameterInputs(); // Re-render inputs with reset state
        performCalculation();    // Recalculate pension
        syncCalculatorToChat?.();
    };

    paramContainer.appendChild(resetBtn);

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

        // 💡 Visa som procent om etiketten innehåller %
        const displayValue = (label.textContent.includes('%') && typeof scenarioObj[field] === 'number')
            ? (scenarioObj[field] * 100).toFixed(2)
            : scenarioObj[field];
        input.value = displayValue;

        input.removeAttribute('readonly');


        // 🧠 Spara tillbaka i calculatorState och trigga omräkning
        input.addEventListener('input', () => {
            const raw = parseFloat(input.value.replace(',', '.'));
            if (!isNaN(raw)) {
                calculatorState[field] = label.textContent.includes('%') ? raw / 100 : raw;
                performCalculation();
                if (typeof syncCalculatorToChat === 'function') {
                    syncCalculatorToChat();
                }
            }
        });

        col.appendChild(label);
        col.appendChild(input);
        scenarioRow.appendChild(col);
        scenarioCount++;

                
    });
    paramContainer.appendChild(advDiv);
}
// Force-load default scenario values into calculatorState
function preloadScenarioDefaults() {
    const defaults = calculationParameters[currentAgreement].scenarios[currentScenario];
    Object.keys(defaults).forEach(key => {
        if (calculatorState[key] === undefined && typeof defaults[key] === 'number') {
            calculatorState[key] = defaults[key];
        }
    });
}

function performCalculation() {
    if (!currentAgreement || !currentScenario) return;
    const scenarioObj = calculationParameters[currentAgreement].scenarios[currentScenario];

    const retirementAge = Number(calculatorState['retirement_age'] ?? scenarioObj.default_retirement_age ?? 65);
    const age = Number(calculatorState['age'] ?? 40);
    const salary = Number(calculatorState['salary'] ?? 50000);
    const growth = Number(calculatorState['default_return_rate'] ?? scenarioObj.default_return_rate ?? 0.019);
    const adminFee = Number(calculatorState['admin_fee_percentage'] ?? scenarioObj.admin_fee_percentage ?? 0);
    const salaryExchange = Number(calculatorState['salary_exchange'] ?? 0);
    const salaryExchangePremium = Number(calculatorState['salary_exchange_premium'] ?? 0);

    const rateBelow = Number(calculatorState['contribution_rate_below_cap'] ?? scenarioObj.contribution_rate_below_cap ?? 0);
    const rateAbove = Number(calculatorState['contribution_rate_above_cap'] ?? scenarioObj.contribution_rate_above_cap ?? 0);
    const incomeCap = Number(calculatorState['income_cap_base_amount'] ?? scenarioObj.income_cap_base_amount ?? 7.5);
    const baseAmount = Number(calculatorState['income_base_amount'] ?? scenarioObj.income_base_amount ?? 74000);

    const annualSalary = salary * 12;
    const cap = incomeCap * baseAmount;

    const belowCap = Math.min(annualSalary, cap);
    const aboveCap = Math.max(0, annualSalary - cap);

    const belowCapContribution = belowCap * rateBelow;
    const aboveCapContribution = aboveCap * rateAbove;

    const lvxContribution = salaryExchange * 12 * (salaryExchangePremium / 100);

    const annualContribution = belowCapContribution + aboveCapContribution + lvxContribution;
    const monthlyContribution = annualContribution / 12;

    const yearsToPension = retirementAge - age;
    if (scenarioObj.type === 'förmånsbestämd' && Array.isArray(scenarioObj.defined_benefit_levels)) {
        
        const salary = Number(calculatorState['salary'] ?? 50000);  // 👈 MOVE IT HERE!
        const years = calculatorState['years_of_service'] || 0;
        let percent = 0;
        scenarioObj.defined_benefit_levels.forEach(level => {
            const yearsCond = level.years;
            const percentVal = level.percent;
        
            if (typeof yearsCond === 'string') {
                if (yearsCond.startsWith('<=') && years <= parseInt(yearsCond.slice(2))) {
                    percent = percentVal;
                } else if (yearsCond.startsWith('<') && years < parseInt(yearsCond.slice(1))) {
                    percent = percentVal;
                } else if (yearsCond.startsWith('>=') && years >= parseInt(yearsCond.slice(2))) {
                    percent = percentVal;
                } else if (yearsCond.startsWith('>') && years > parseInt(yearsCond.slice(1))) {
                    percent = percentVal;
                }
            } else if (typeof yearsCond === 'number' && years >= yearsCond) {
                percent = percentVal;
            }
        });
        
        
    
        const annualPension = salary * 12 * percent;
        const monthlyPension = annualPension / 12;
        const total = annualPension * 20;
    
        // Display results directly instead of using showResultCards
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
              <div style="font-size:2.1em; font-weight:700; color:#43a047;">-</div>
              <div style="color:#43a047; font-size:1.15em; margin-bottom:2px;">kr/år</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Årlig avsättning</div>
            </div>
            <div class="result-block" style="flex:1 1 170px; min-width:150px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#1976d2;">-</div>
              <div style="color:#1976d2; font-size:1.15em; margin-bottom:2px;">kr/mån</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Månatlig avsättning</div>
            </div>
            <div class="result-block" style="flex:1 1 120px; min-width:110px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#b28900;">${isNaN(yearsToPension) ? '-' : yearsToPension}</div>
              <div style="color:#b28900; font-size:1.15em; margin-bottom:2px;">år</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">År till pension</div>
            </div>
            <div class="result-block" style="flex:1 1 180px; min-width:150px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#0d47a1;">${isNaN(total) ? '-' : total.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
              <div style="color:#0d47a1; font-size:1.15em; margin-bottom:2px;">kr</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Totalt kapital</div>
            </div>
            <div class="result-block" style="flex:1 1 180px; min-width:150px; text-align:center;">
              <div style="font-size:2.1em; font-weight:700; color:#b28900;">${isNaN(monthlyPension) ? '-' : monthlyPension.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
              <div style="color:#b28900; font-size:1.15em; margin-bottom:2px;">kr/mån</div>
              <div style="font-size:1.07em; color:#222; margin-bottom:2px;">🧓 Månatlig pension</div>
            </div>
          </div>
        `;
        return;
    }
    
    
    // Growth simulation
    let total = 0;
    let yearlyResults = [];

    for (let i = 1; i <= yearsToPension; i++) {
        // Apply only growth to compounding, do NOT subtract adminFee from growth
        let compounded = annualContribution * Math.pow(1 + growth, yearsToPension - i);
        // Optionally, deduct admin fee as a percentage of the balance after growth (if required by business logic)
        // compounded = compounded * (1 - adminFee); // Uncomment if admin fee should be applied after growth
        total += compounded;

        yearlyResults.push({
            year: i,
            value: total
        });
    }


    const monthlyPension = total / (20 * 12);


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
          <div style="font-size:2.1em; font-weight:700; color:#43a047;">${isNaN(annualContribution) ? '-' : annualContribution.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style="color:#43a047; font-size:1.15em; margin-bottom:2px;">kr/år</div>
          <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Årlig avsättning</div>
        </div>
        <div class="result-block" style="flex:1 1 170px; min-width:150px; text-align:center;">
          <div style="font-size:2.1em; font-weight:700; color:#1976d2;">${isNaN(monthlyContribution) ? '-' : monthlyContribution.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style="color:#1976d2; font-size:1.15em; margin-bottom:2px;">kr/mån</div>
          <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Månatlig avsättning</div>
        </div>
        <div class="result-block" style="flex:1 1 120px; min-width:110px; text-align:center;">
          <div style="font-size:2.1em; font-weight:700; color:#b28900;">${isNaN(yearsToPension) ? '-' : yearsToPension}</div>
          <div style="color:#b28900; font-size:1.15em; margin-bottom:2px;">år</div>
          <div style="font-size:1.07em; color:#222; margin-bottom:2px;">År till pension</div>
        </div>
        <div class="result-block" style="flex:1 1 180px; min-width:150px; text-align:center;">
          <div style="font-size:2.1em; font-weight:700; color:#0d47a1;">${isNaN(total) ? '-' : total.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style="color:#0d47a1; font-size:1.15em; margin-bottom:2px;">kr</div>
          <div style="font-size:1.07em; color:#222; margin-bottom:2px;">Totalt kapital</div>
        </div>
        <div class="result-block" style="flex:1 1 180px; min-width:150px; text-align:center;">
          <div style="font-size:2.1em; font-weight:700; color:#b28900;">${isNaN(monthlyPension) ? '-' : monthlyPension.toLocaleString('sv-SE', {maximumFractionDigits:0})}</div>
          <div style="color:#b28900; font-size:1.15em; margin-bottom:2px;">kr/mån</div>
          <div style="font-size:1.07em; color:#222; margin-bottom:2px;">🧓 Månatlig pension</div>
        </div>
      </div>
      ${aboveCap > 0 ? `
        <div class='row mt-3'><div class='col-12'>
          <div class='alert alert-info' style='font-size:1.05em;'>
            <strong>⚖️ Inkomst över tak:</strong> 
            <br>Lön över gräns: <strong>${aboveCap.toLocaleString('sv-SE')} kr/år</strong> 
            <br>Premie: ${rateAbove * 100}% → <strong>${aboveCapContribution.toLocaleString('sv-SE')} kr/år</strong>
          </div>
        </div></div>` : ''}
    `;
}



function syncCalculatorToChat() {
    // Send calculator state to chat context (MVP implementation)
    if (window && typeof window.postMessage === 'function') {
        window.postMessage({ type: 'calculator_update', data: { ...calculatorState } }, '*');
    }
}

function syncChatToCalculator(params) {
    // Called when chat detects calculation intent and extracts parameters
    if (params && typeof params === 'object') {
        Object.keys(params).forEach(key => {
            calculatorState[key] = params[key];
        });
    }
    renderParameterInputs();
    preloadScenarioDefaults();
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
        calculatorState.scenario = currentScenario;  // ✅ This is the missing link
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
