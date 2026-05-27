// ==========================================================================
// ARCHICOLOR PRO - CORE FRONTEND SYSTEM
// ==========================================================================

var API_BASE = window.API_BASE || "";
window.API_BASE = API_BASE;

// Global App State
const state = {
    projectTypes: [],
    brands: [],
    collections: [],
    colors: [],
    savedDesigns: [],
    
    // Filters and Pagination
    filters: {
        projectTypeId: "",
        floors: "",
        facades: "",
        brandId: "",
        category: "",
        searchTemplates: "",
        searchColors: ""
    },
    
    pagination: {
        templatesPage: 1,
        templatesHasMore: true,
        colorsPage: 1,
        colorsHasMore: true
    },
    
    // Active states
    activeCollection: null,
    activeLayer: null,
    selectedColors: {}, // { [layerId]: hex_code }
    layerImageCache: {}, // { [layerId]: HTMLImageElement }
    
    // Coloring History (Undo / Redo)
    history: [],
    historyIndex: -1,
    
    // Blending Mode state
    blendMethod: "css", // "canvas" or "css"
    compareActive: false, // Comparison mode toggle
    
    // Loading guards
    isLoadingTemplates: false,
    isLoadingColors: false,
    isLoadingCanvas: false,
    
    // AI Color Tool state
    aiColorTool: {
        currentStep: 1, // 1, 2, or 3
        projectType: null, // "interior" or "exterior"
        uploadedImage: null, // base64 or blob
        selectedPart: "wall-main",
        selectedColor: null,
        selectedColors: {},
        detectedAreasRequestKey: null,
        imageId: null,
        lastClick: null,
        areaClicks: {},
        isProcessing: false,
        zoom: 1.0, // Zoom level for preview images
        maxZoom: 3.0, // Maximum zoom level
        minZoom: 1.0  // Minimum zoom level
    }
};

// DOM Elements cache
const DOM = {
    projectTypeFilter: document.getElementById("filter-project-type"),
    floorsFilter: document.getElementById("filter-floors"),
    facadesFilter: document.getElementById("filter-facades"),
    brandFilter: document.getElementById("filter-brand"),
    
    searchTemplates: document.getElementById("search-templates"),
    searchColors: document.getElementById("search-colors"),
    
    templatesGrid: document.getElementById("templates-grid"),
    templatesCount: document.getElementById("templates-count"),
    
    colorsGrid: document.getElementById("colors-grid"),
    colorsLoadMore: document.getElementById("colors-load-more"),
    colorsGridContainer: document.getElementById("colors-grid-container"),
    colorCategoryChips: document.querySelectorAll(".cat-chip"),
    
    visualizerContainer: document.getElementById("visualizer-container"),
    canvasWrapperReal: document.getElementById("canvas-wrapper-real"),
    cssLayersWrapper: document.getElementById("css-layers-wrapper"),
    mainCanvas: document.getElementById("main-drawing-canvas"),
    canvasLoader: document.getElementById("canvas-loader"),
    
    currentHouseName: document.getElementById("current-house-name"),
    currentHouseDesc: document.getElementById("current-house-desc"),
    layersList: document.getElementById("layers-list"),
    
    blendMethodToggle: document.getElementById("blend-method-toggle"),
    modeCanvasSpan: document.getElementById("mode-canvas"),
    modeCssSpan: document.getElementById("mode-css"),
    
    btnUndo: document.getElementById("btn-undo"),
    btnRedo: document.getElementById("btn-redo"),
    btnReset: document.getElementById("btn-reset"),
    btnCompare: document.getElementById("btn-compare"),
    btnSave: document.getElementById("btn-save"),
    btnExport: document.getElementById("btn-export"),
    
    toast: document.getElementById("toast-notification"),
    toastMsg: document.getElementById("toast-message"),
    
    // Upgrade elements: Sidebar Tabs
    tabTemplates: document.getElementById("tab-templates"),
    tabSaved: document.getElementById("tab-saved"),
    tabContentTemplates: document.getElementById("tab-content-templates"),
    tabContentSaved: document.getElementById("tab-content-saved"),
    savedDesignsList: document.getElementById("saved-designs-list"),
    savedDesignsCount: document.getElementById("saved-designs-count"),
    
    // New navigation/view elements matching aicolor.vn
    tabAi: document.getElementById("tab-ai"),
    tabVisualizer: document.getElementById("tab-visualizer"),
    tabContentAi: document.getElementById("tab-content-ai"),
    tabContentVisualizer: document.getElementById("tab-content-visualizer"),
    noProjectPlaceholder: document.getElementById("no-project-placeholder"),
    workspaceEditorGrid: document.getElementById("workspace-editor-grid"),
    
    // Upgrade elements: Compare placeholders
    canvasWrapperOriginal: document.getElementById("canvas-wrapper-original"),
    cssLayersOriginalWrapper: document.getElementById("css-layers-original-wrapper"),
    originalCanvas: document.getElementById("original-drawing-canvas"),
    
    // Upgrade elements: Modal for Save Design
    saveDesignModal: document.getElementById("save-design-modal"),
    saveDesignName: document.getElementById("save-design-name"),
    btnConfirmSave: document.getElementById("btn-confirm-save"),
    btnCancelSave: document.getElementById("btn-cancel-save"),
    btnCloseModal: document.getElementById("btn-close-modal")
};

// ==========================================================================
// DEBOUNCE UTILITY
// ==========================================================================
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function aiCompressImageDataUrl(dataUrl, maxDimension = 1600, quality = 0.88) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            const scale = Math.min(1, maxDimension / Math.max(img.width, img.height));
            if (scale >= 1 && dataUrl.length < 2.5 * 1024 * 1024) {
                resolve(dataUrl);
                return;
            }
            
            const canvas = document.createElement("canvas");
            canvas.width = Math.max(1, Math.round(img.width * scale));
            canvas.height = Math.max(1, Math.round(img.height * scale));
            const ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            resolve(canvas.toDataURL("image/jpeg", quality));
        };
        img.onerror = () => resolve(dataUrl);
        img.src = dataUrl;
    });
}

function ensureAiProcessingOverlay() {
    const viewport = document.querySelector(".ai-preview-viewport");
    if (!viewport) return null;
    
    let overlay = document.getElementById("ai-processing-overlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "ai-processing-overlay";
        overlay.className = "ai-processing-overlay";
        overlay.setAttribute("aria-live", "polite");
        overlay.setAttribute("aria-hidden", "true");
        overlay.innerHTML = `
            <div class="ai-processing-box">
                <i class="fa-solid fa-spinner fa-spin"></i>
                <span>AI loading</span>
            </div>
        `;
        viewport.appendChild(overlay);
    }
    return overlay;
}

function setAiProcessing(isProcessing) {
    state.aiColorTool.isProcessing = isProcessing;
    const viewport = document.querySelector(".ai-preview-viewport");
    const overlay = ensureAiProcessingOverlay();
    const generateBtn = document.querySelector(".btn-generate");
    const refreshBtn = document.querySelector(".btn-refresh");
    const addImageBtn = document.querySelector(".btn-add-image");
    const fileInput = document.getElementById("ai-file-input");
    
    viewport?.classList.toggle("ai-processing", isProcessing);
    if (overlay) overlay.setAttribute("aria-hidden", String(!isProcessing));
    if (generateBtn) generateBtn.disabled = isProcessing;
    if (refreshBtn) refreshBtn.disabled = isProcessing;
    if (addImageBtn) addImageBtn.disabled = isProcessing;
    if (fileInput) fileInput.disabled = isProcessing;
    
    document.querySelectorAll(".type-button, .color-part-item, .color-palette-item").forEach(el => {
        if ("disabled" in el) el.disabled = isProcessing;
        el.classList.toggle("is-disabled", isProcessing);
    });
}

function aiChooseAnotherImage() {
    if (state.aiColorTool.isProcessing) {
        showToast('AI đang xử lý, vui lòng chờ kết quả.', 'error');
        return;
    }

    const fileInput = document.getElementById("ai-file-input");
    if (!fileInput) return;

    fileInput.value = "";
    fileInput.click();
}

// ==========================================================================
// AI COLOR TOOL FUNCTIONS
// ==========================================================================
const paintAreas = {
    interior: [
        { id: 'wall-main', label: 'Màu tường chính', aiLabel: 'main wall / primary interior wall surface / tường chính' },
        { id: 'accent', label: 'Màu tường nhấn', aiLabel: 'accent wall / feature wall / tường nhấn' },
        { id: 'ceiling', label: 'Màu trần nhà', aiLabel: 'ceiling paintable surface / trần nhà' }
    ],
    exterior: [
        { id: 'wall-main', label: 'Màu tường chính', aiLabel: 'main exterior wall / facade wall paintable surface / tường chính mặt tiền' },
        { id: 'trim', label: 'Màu phào chỉ', aiLabel: 'trim / molding / cornice / border / phào chỉ viền' },
        { id: 'column', label: 'Màu cột', aiLabel: 'column / pillar / pilaster paintable surface / cột' },
        { id: 'detail', label: 'Màu chi tiết', aiLabel: 'architectural detail / decorative detail / small paintable accent details / chi tiết kiến trúc' }
    ]
};

function aiGetAreaLabel(areaId) {
    const type = state.aiColorTool.projectType;
    const areas = paintAreas[type] || [];
    const area = areas.find(item => item.id === areaId);
    return area ? area.label : areaId;
}

function aiGetAreaPromptLabel(areaId) {
    const type = state.aiColorTool.projectType;
    const areas = paintAreas[type] || [];
    const area = areas.find(item => item.id === areaId);
    return area ? (area.aiLabel || area.label) : areaId;
}

function aiBuildRequestedAreas(colors) {
    return Object.keys(colors).map(areaId => ({
        id: areaId,
        label: aiGetAreaPromptLabel(areaId),
        displayLabel: aiGetAreaLabel(areaId),
        hex: colors[areaId]
    }));
}

function aiGetRequestedAreasKey(requestedAreas) {
    return JSON.stringify(requestedAreas.map(area => [area.id, area.label]));
}

function aiUpdatePaletteSelection() {
    const selectedHex = state.aiColorTool.selectedColors[state.aiColorTool.selectedPart] || null;
    state.aiColorTool.selectedColor = selectedHex;
    
    document.querySelectorAll('.color-palette-item').forEach(item => {
        item.classList.toggle('selected', !!selectedHex && item.dataset.hexColor === selectedHex);
    });
}

function aiRenderPaintAreas(type) {
    const container = document.getElementById('ai-paint-areas');
    if (!container) return;
    
    const areas = paintAreas[type] || paintAreas.interior;
    container.innerHTML = '';
    
    areas.forEach((area, index) => {
        const selectedHex = state.aiColorTool.selectedColors[area.id];
        const swatchStyle = selectedHex ? `background: ${selectedHex}; border: 1px solid #ccc;` : '';
        const swatchClass = selectedHex ? 'color-swatch' : 'color-swatch unpainted';
        const btn = document.createElement('button');
        btn.className = `color-part-item ${index === 0 ? 'active' : ''}`;
        btn.dataset.areaId = area.id;
        btn.onclick = function(e) { aiSelectPart(e.target.closest('.color-part-item'), area.id); };
        btn.innerHTML = `
            <span>${area.label}</span>
            <div class="${swatchClass}" style="${swatchStyle}" title="${selectedHex || 'Chưa sơn'}"></div>
            <small class="part-paint-status">${selectedHex || 'Chưa sơn'}</small>
        `;
        container.appendChild(btn);
    });
    
    // Add custom input button
    const customBtn = document.createElement('button');
    customBtn.className = 'color-part-item color-part-custom-trigger';
    customBtn.innerHTML = `
        <span>+ Tự nhập</span>
        <div class="color-swatch unpainted" title="Chưa sơn"></div>
        <small class="part-paint-status">Chưa sơn</small>
    `;
    customBtn.onclick = function(e) { aiShowCustomInput(); };
    container.appendChild(customBtn);
    
    // Add hidden custom input form to body (if not already present)
    if (!document.getElementById('ai-custom-input-form')) {
        const customForm = document.createElement('div');
        customForm.id = 'ai-custom-input-form';
        customForm.className = 'ai-custom-input-form';
        customForm.style.display = 'none';
        customForm.innerHTML = `
            <div class="custom-input-container">
                <label for="ai-custom-part-name">Nhập tên vùng cần sơn:</label>
                <input type="text" id="ai-custom-part-name" placeholder="Ví dụ: Cửa chính, Hàng rào..." maxlength="50">
                <div class="custom-input-buttons">
                    <button class="btn-confirm-custom" onclick="aiConfirmCustomInput()">Thêm</button>
                    <button class="btn-cancel-custom" onclick="aiCancelCustomInput()">Hủy</button>
                </div>
            </div>
        `;
        document.body.appendChild(customForm);
    }
    
    // Set first area as selected and update the title
    state.aiColorTool.selectedPart = areas[0].id;
    state.aiColorTool.selectedColor = state.aiColorTool.selectedColors[areas[0].id] || null;
    document.getElementById('ai-selected-part-name').textContent = areas[0].label;
    aiUpdatePaletteSelection();
}

function aiShowCustomInput() {
    const form = document.getElementById('ai-custom-input-form');
    if (form) {
        form.style.display = 'flex';
        document.getElementById('ai-custom-part-name').focus();
    }
}

function aiCancelCustomInput() {
    const form = document.getElementById('ai-custom-input-form');
    if (form) {
        form.style.display = 'none';
        document.getElementById('ai-custom-part-name').value = '';
    }
}

function aiConfirmCustomInput() {
    const customName = document.getElementById('ai-custom-part-name').value.trim();
    
    if (!customName) {
        showToast('Vui lòng nhập tên vùng cần sơn', 'error');
        return;
    }
    
    // Get current type
    const type = state.aiColorTool.projectType;
    const customId = 'custom-' + Date.now();
    
    // Add to paintAreas
    if (!paintAreas[type]) {
        paintAreas[type] = [];
    }
    paintAreas[type].push({ id: customId, label: customName });
    window.globalDetectedAreas = [];
    state.aiColorTool.detectedAreasRequestKey = null;
    
    // Re-render paint areas
    aiRenderPaintAreas(type);
    
    // Cancel form
    aiCancelCustomInput();
    
    // Select the newly added custom area
    const newBtn = document.querySelector(`.color-part-item[data-area-id="${customId}"]`);
    if (newBtn) {
        aiSelectPart(newBtn, customId);
    }
    
    showToast(`Đã thêm vùng "${customName}"`, 'success');
}

function aiSetType(type) {
    console.log('aiSetType called with:', type);
    
    state.aiColorTool.projectType = type;
    window.globalDetectedAreas = [];
    state.aiColorTool.detectedAreasRequestKey = null;
    
    // Update UI - mark buttons
    document.querySelectorAll('.type-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Find the clicked button and mark it as active
    const buttons = document.querySelectorAll('.type-button');
    buttons.forEach(btn => {
        if (btn.getAttribute('onclick').includes(`'${type}'`)) {
            btn.classList.add('active');
        }
    });
    
    // Start with no selected colors. White swatches are only visual defaults;
    // untouched areas must not be sent to the painter.
    state.aiColorTool.selectedColors = {};
    state.aiColorTool.areaClicks = {};
    state.aiColorTool.lastClick = null;
    const areas = paintAreas[type] || paintAreas.interior;
    console.log('Paint areas for type:', type, areas);
    
    console.log('Initialized selectedColors:', state.aiColorTool.selectedColors);
    
    // Render paint areas for this type
    aiRenderPaintAreas(type);
    
    // Go to step 3 (color assignment)
    aiGoToStep(3);
}

function aiGoToStep(step) {
    state.aiColorTool.currentStep = step;
    
    // Hide all steps
    document.getElementById('ai-step-1').style.display = 'none';
    document.getElementById('ai-step-2').style.display = 'none';
    document.getElementById('ai-step-3').style.display = 'none';
    
    // Show current step
    document.getElementById('ai-step-' + step).style.display = 'block';
    
    // Update preview status
    if (step === 1) {
        document.getElementById('ai-preview-status').textContent = 'Chưa có dự án nào được chọn';
    } else if (step === 2) {
        document.getElementById('ai-preview-status').textContent = 'Đã tải ảnh. Vui lòng chọn loại công trình.';
    } else if (step === 3) {
        document.getElementById('ai-preview-status').textContent = 'Ảnh gốc đã tải lên. Áp dụng màu để xem kết quả từ AI.';
        // Load colors only when step 3 is displayed
        aiLoadColors();
    }
}

function aiResetAll() {
    // Reset AI Color Tool state
    state.aiColorTool = {
        currentStep: 1,
        projectType: null,
        uploadedImage: null,
        selectedPart: "wall-main",
        selectedColor: null,
        selectedColors: {},
        detectedAreasRequestKey: null,
        imageId: null,
        lastClick: null,
        areaClicks: {},
        isProcessing: false,
        zoom: 1.0,
        maxZoom: 3.0,
        minZoom: 1.0
    };
    
    // Clear file input
    const fileInput = document.getElementById("ai-file-input");
    if (fileInput) {
        fileInput.value = "";
    }
    
    // Clear global detected areas
    window.globalDetectedAreas = [];
    
    // Hide preview elements
    const previewImage = document.getElementById('ai-preview-image');
    const comparisonContainer = document.getElementById('ai-comparison-container');
    const previewControls = document.getElementById('ai-preview-controls');
    const previewPlaceholder = document.getElementById('ai-preview-placeholder');
    
    if (previewImage) previewImage.style.display = 'none';
    if (comparisonContainer) comparisonContainer.style.display = 'none';
    if (previewControls) previewControls.style.display = 'none';
    if (previewPlaceholder) previewPlaceholder.style.display = 'block';
    
    // Reset step UI
    aiGoToStep(1);
    
    // Show success message
    showToast('Đã làm mới trang', 'success');
}

function aiSelectPart(element, partId) {
    state.aiColorTool.selectedPart = partId;
    state.aiColorTool.selectedColor = state.aiColorTool.selectedColors[partId] || null;
    state.aiColorTool.lastClick = state.aiColorTool.areaClicks[partId] || null;
    
    // Update UI
    document.querySelectorAll('.color-part-item').forEach(btn => {
        btn.classList.remove('active');
    });
    element.classList.add('active');
    
    // Update the selected part name
    const partLabel = element.querySelector('span').textContent;
    document.getElementById('ai-selected-part-name').textContent = partLabel;
    
    aiUpdatePaletteSelection();
}

async function aiSelectColor(hexColor) {
    state.aiColorTool.selectedColor = hexColor;
    state.aiColorTool.selectedColors[state.aiColorTool.selectedPart] = hexColor;
    window.globalDetectedAreas = [];
    state.aiColorTool.detectedAreasRequestKey = null;
    aiUpdatePaletteSelection();
    
    // Update color swatch in the parts list
    const partItem = document.querySelector('.color-part-item.active .color-swatch');
    if (partItem) {
        partItem.style.background = hexColor;
        partItem.classList.remove('unpainted');
        partItem.title = hexColor;
    }
    
    const statusItem = document.querySelector('.color-part-item.active .part-paint-status');
    if (statusItem) {
        statusItem.textContent = hexColor;
        statusItem.style.color = 'var(--color-primary)';
    }


    
    showToast('Đã chọn màu cho phần này', 'success');
}

const AI_DEFAULT_MASK_AREAS = [
    { id: 'wall-main', label: 'Tuong chinh' },
    { id: 'roof', label: 'Mai nha' },
    { id: 'column', label: 'Cot' },
    { id: 'trim', label: 'Chi nha / phao chi' },
    { id: 'window-frame', label: 'Khung cua so' },
    { id: 'door', label: 'Cua' },
    { id: 'ceiling', label: 'Tran nha' },
    { id: 'accent', label: 'Mang nhan / diem nhan' }
];

async function aiAnalyzeInitialMasks(imageDataUrl) {
    const savedApiKey = localStorage.getItem("gemini_api_key");
    const payload = {
        image: imageDataUrl,
        project_type: state.aiColorTool.projectType,
        requested_areas: AI_DEFAULT_MASK_AREAS
    };
    if (savedApiKey) payload.api_key = savedApiKey;

    const response = await fetch(`${API_BASE}/api/ai-colorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!result.success) {
        throw new Error(result.detail || result.message || result.error_type || 'Khong the tao AI layer mask');
    }
    const data = result.data || {};
    const detectedAreas = data.detected_areas || data.detectedAreas || [];
    if (!Array.isArray(detectedAreas) || detectedAreas.length === 0) {
        throw new Error('AI chua nhan dien duoc vung son de tao mask.');
    }
    window.globalDetectedAreas = detectedAreas;
    state.aiColorTool.detectedAreasRequestKey = aiGetRequestedAreasKey(AI_DEFAULT_MASK_AREAS);
    return detectedAreas;
}

async function aiCreatePaintSession(imageDataUrl) {
    const payload = { image: imageDataUrl };
    const response = await fetch(`${API_BASE}/api/upload-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!result.success) {
        throw new Error(result.detail || result.message || 'Không thể tạo mask cho ảnh');
    }
    state.aiColorTool.imageId = result.image_id;
    state.aiColorTool.lastClick = null;
    return result;
}

function aiGetImageClickCoords(event, imageEl) {
    const rect = imageEl.getBoundingClientRect();
    const naturalWidth = imageEl.naturalWidth || imageEl.clientWidth;
    const naturalHeight = imageEl.naturalHeight || imageEl.clientHeight;
    const scale = Math.min(rect.width / naturalWidth, rect.height / naturalHeight);
    const renderedWidth = naturalWidth * scale;
    const renderedHeight = naturalHeight * scale;
    const offsetX = (rect.width - renderedWidth) / 2;
    const offsetY = (rect.height - renderedHeight) / 2;
    const localX = event.clientX - rect.left - offsetX;
    const localY = event.clientY - rect.top - offsetY;
    const x = Math.round((localX / renderedWidth) * naturalWidth);
    const y = Math.round((localY / renderedHeight) * naturalHeight);
    return {
        x: Math.max(0, Math.min(naturalWidth - 1, x)),
        y: Math.max(0, Math.min(naturalHeight - 1, y))
    };
}

function aiRegisterPaintClick(event) {
    const imageEl = event.currentTarget;
    if (!state.aiColorTool.imageId || !imageEl) return;
    event.preventDefault();
    event.stopPropagation();
    state.aiColorTool.lastClick = aiGetImageClickCoords(event, imageEl);
    state.aiColorTool.areaClicks[state.aiColorTool.selectedPart] = state.aiColorTool.lastClick;
    if (state.aiColorTool.selectedColor) {
        aiApplyPaintAtClick();
        return;
    }
    document.getElementById('ai-preview-status').textContent = `Đã chọn vùng tại X:${state.aiColorTool.lastClick.x}, Y:${state.aiColorTool.lastClick.y}. Chọn màu rồi bấm tạo ảnh phối màu.`;
    showToast('Đã chọn vùng cần sơn trên ảnh', 'success');
}

async function aiApplyPaintAtClick() {
    if (state.aiColorTool.isProcessing) {
        showToast('AI đang xử lý, vui lòng chờ kết quả.', 'error');
        return;
    }
    if (!state.aiColorTool.imageId) {
        showToast('Vui lòng tải ảnh lên trước.', 'error');
        return;
    }
    if (!state.aiColorTool.lastClick) {
        showToast('Vui lòng click trực tiếp vào vùng muốn sơn cho phần đang chọn.', 'error');
        return;
    }
    if (!state.aiColorTool.selectedColor) {
        showToast('Vui lòng chọn màu HEX trước khi sơn.', 'error');
        return;
    }

    setAiProcessing(true);
    showToast('Đang sơn vùng đã click bằng mask AI...', 'success');
    try {
        const response = await fetch(`${API_BASE}/api/apply-paint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_id: state.aiColorTool.imageId,
                x: state.aiColorTool.lastClick.x,
                y: state.aiColorTool.lastClick.y,
                color: state.aiColorTool.selectedColor
            })
        });
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.detail || result.message || result.error_type || 'Không thể sơn vùng đã chọn');
        }

        const originalImg = document.getElementById('ai-original-image');
        const generatedImg = document.getElementById('ai-generated-image');
        const comparisonContainer = document.getElementById('ai-comparison-container');
        const previewPlaceholder = document.getElementById('ai-preview-placeholder');
        const previewImage = document.getElementById('ai-preview-image');

        if (originalImg) originalImg.src = state.aiColorTool.uploadedImage;
        if (generatedImg) generatedImg.src = result.data?.image || result.image;
        if (comparisonContainer) {
            comparisonContainer.style.display = 'flex';
            comparisonContainer.style.transform = 'scale(1)'; // Reset zoom
        }
        if (previewPlaceholder) previewPlaceholder.style.display = 'none';
        if (previewImage) previewImage.style.display = 'none';
        
        // Reset zoom
        state.aiColorTool.zoom = 1.0;
        aiApplyZoom();
        
        aiInitializeComparisonSlider();

        document.getElementById('ai-preview-status').textContent = 'Đã sơn vùng click bằng mask đã tạo sẵn. Có thể click vùng khác và chọn màu tiếp.';
        showToast('Ảnh phối màu đã được tạo thành công!', 'success');
    } catch (error) {
        console.error('Apply paint error:', error);
        showToast('❌ ' + error.message, 'error');
    } finally {
        setAiProcessing(false);
    }
}

async function aiLoadColors() {
    const container = document.getElementById('ai-color-palette');
    if (!container) return;
    
    const renderColors = (colors) => {
        container.innerHTML = '';
        colors.forEach((color) => {
            const btn = document.createElement('button');
            btn.className = 'color-palette-item';
            btn.style.background = color.hex_code;
            btn.dataset.hexColor = color.hex_code;
            btn.title = `${color.paint_code} - ${color.hex_code}`;
            btn.textContent = color.paint_code;
            btn.onclick = function(e) {
                e.preventDefault();
                aiSelectColor(color.hex_code);
            };
            container.appendChild(btn);
        });
        aiUpdatePaletteSelection();
    };
    
    try {
        // Primary source: danh_sach_mau_son_chuan.json (standard color list)
        const response = await fetch('/static/danh_sach_mau_son_chuan.json');
        const colors = await response.json();
        
        if (Array.isArray(colors) && colors.length > 0) {
            renderColors(colors);
            return;
        }
    } catch (e) {
        console.warn('Failed to load from danh_sach_mau_son_chuan.json:', e);
    }
    
    try {
        // Fallback: /api/colors from database
        const response = await fetch(`${API_BASE}/api/colors?limit=100`);
        const result = await response.json();
        
        if (result.success && result.data && result.data.length > 0) {
            renderColors(result.data);
            return;
        }
    } catch (e) {
        console.warn('Failed to load from /api/colors:', e);
    }
    
    try {
        // Fallback 2: mauson.txt
        const response = await fetch('/mauson.txt');
        const data = await response.json();
        const colors = data.data.colors;
        
        if (colors && colors.length > 0) {
            renderColors(colors);
            return;
        }
    } catch (e) {
        console.warn('Failed to load from mauson.txt:', e);
    }
    
    // No colors could be loaded
    container.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--color-danger);">Lỗi tải danh sách màu</p>';
}

async function aiGenerateColors() {
    if (state.aiColorTool.isProcessing) {
        showToast('AI đang xử lý, vui lòng chờ kết quả.', 'error');
        return;
    }
    
    const type = state.aiColorTool.projectType;
    const image = state.aiColorTool.uploadedImage;
    const colors = state.aiColorTool.selectedColors;
    
    console.log('aiGenerateColors called', {type, hasImage: !!image, colors});
    
    // Detailed validation
    if (!type) {
        showToast('❌ Vui lòng chọn loại công trình (Nội thất/Ngoại thất)', 'error');
        console.error('Missing: projectType');
        return;
    }
    
    if (!image) {
        showToast('❌ Vui lòng tải lên ảnh công trình', 'error');
        console.error('Missing: image');
        return;
    }
    
    // Check image size (max 10MB)
    if (image.length > 10 * 1024 * 1024) {
        showToast('❌ Ảnh quá lớn (tối đa 10MB)', 'error');
        return;
    }
    
    let selectedCount = Object.keys(colors).length;
    if (selectedCount === 0) {
        showToast('❌ Vui lòng chọn ít nhất một màu sơn cho vùng', 'error');
        console.error('No colors selected');
        return;
    }
    
    // Show loading state
    showToast('⏳ Đang phân tích vùng sơn bằng Gemini AI...', 'success');
    setAiProcessing(true);
    
    try {
        const requestedAreas = aiBuildRequestedAreas(colors);
        const savedApiKey = localStorage.getItem("gemini_api_key");
        if (false) {
            const analyzeResult = { success: true, data: { detected_areas: requestedAreas } };
            const requestedAreasKey = aiGetRequestedAreasKey(requestedAreas);
            let detectedAreas = requestedAreas;
        
            console.log('🤖 AI colorize response:', analyzeResult);
            console.log('🤖 AI colorize response JSON:', JSON.stringify(analyzeResult));
            
            if (!analyzeResult.success) {
                const aiError = analyzeResult.detail || analyzeResult.message || analyzeResult.error_type || 'Không thể phân tích vùng sơn bằng AI';
                showToast('❌ ' + aiError, 'error');
                return;
            }
            
            const aiData = analyzeResult.data || {};
            detectedAreas = aiData.detected_areas || aiData.detectedAreas || [];
            console.log('🎯 Detected paint areas:', detectedAreas);
            window.globalDetectedAreas = detectedAreas;
            state.aiColorTool.detectedAreasRequestKey = requestedAreasKey;
            
            if (aiData.space_type && aiData.space_type !== type) {
                console.warn('AI space_type differs from user selection:', aiData.space_type, type);
            }
            
            if (!detectedAreas.length) {
                showToast('❌ AI chưa nhận diện được vùng có thể sơn trong ảnh này.', 'error');
                return;
            }
        }
        
        showToast('⏳ Đang tạo ảnh phối màu với mask AI...', 'success');
        
        showToast('Dang tao anh AI bang Gemini 2.5 Flash Image...', 'success');

        // Build request payload
        const payload = {
            image: image,
            projectType: type,
            paintAreas: colors,
            detectedAreas: requestedAreas,
            imageProvider: 'gemini'
        };
        if (savedApiKey) payload.api_key = savedApiKey;
        
        console.log('📤 Request Payload Debug:', {
            projectType: payload.projectType,
            imageSizeKB: Math.round(payload.image.length / 1024),
            paintAreasKeys: Object.keys(payload.paintAreas),
            paintAreasCount: Object.keys(payload.paintAreas).length,
            paintAreasData: payload.paintAreas,
            requestedAreas: requestedAreas,
            imageProvider: payload.imageProvider
        });
        
        const response = await fetch(`${API_BASE}/api/ai/generate-colors`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        console.log('📥 API Response status:', response.status);
        const result = await response.json();
        console.log('📋 Full API Response:', result);
        console.log('API returned:', result.success ? 'SUCCESS' : 'FAILED', result.message || result.error_type);
        
        if (result.data && result.data.paint_meta) {
            console.log('🎨 Paint meta:', result.data.paint_meta);
        }
        
        if (result.details) {
            console.error('❌ Validation Errors:', result.details);
        }
        
        if (result.success && result.data && result.data.image) {
            // Display the generated image with comparison slider
            const originalImg = document.getElementById('ai-original-image');
            const generatedImg = document.getElementById('ai-generated-image');
            const comparisonContainer = document.getElementById('ai-comparison-container');
            const previewPlaceholder = document.getElementById('ai-preview-placeholder');
            const previewControls = document.getElementById('ai-preview-controls');
            
            if (originalImg && generatedImg && comparisonContainer) {
                // Set original image (uploaded)
                originalImg.src = state.aiColorTool.uploadedImage;
                
                // Set generated image (from AI)
                generatedImg.src = result.data.image;
                
                // Show comparison slider, hide placeholder
                comparisonContainer.style.display = 'flex';
                comparisonContainer.style.transform = 'scale(1)'; // Reset zoom transform
                previewPlaceholder.style.display = 'none';
                
                // Show preview controls for zoom
                if (previewControls) previewControls.style.display = 'flex';
                
                // Reset zoom
                state.aiColorTool.zoom = 1.0;
                aiApplyZoom();
                
                // Initialize slider
                aiInitializeComparisonSlider();
            }
            
            document.getElementById('ai-preview-status').textContent = '👉 Kéo thanh để so sánh ảnh gốc và ảnh phối màu';
            showToast('✨ Ảnh phối màu đã được tạo thành công!', 'success');
        } else {
            const errorMsg = result.detail || result.message || result.error_type || 'Không thể tạo ảnh phối màu';
            console.error('API Error:', errorMsg);
            showToast('❌ ' + errorMsg, 'error');
            
            // Show detailed error for debugging
            if (errorMsg.includes('API Key')) {
                console.warn('💡 Mẹo: Kiểm tra GEMINI_API_KEY trong file .env');
            }
        }
    } catch (error) {
        console.error('Network/Parse Error:', error);
        showToast('❌ Lỗi kết nối: ' + error.message, 'error');
    } finally {
        setAiProcessing(false);
    }
}

// ==========================================================================
// TOAST NOTIFICATIONS
// ==========================================================================
function showToast(message, type = "success") {
    DOM.toastMsg.textContent = message;
    const icon = DOM.toast.querySelector(".toast-icon");
    
    if (type === "success") {
        DOM.toast.style.borderColor = "var(--color-success)";
        icon.className = "fa-solid fa-circle-check toast-icon";
        icon.style.color = "var(--color-success)";
    } else {
        DOM.toast.style.borderColor = "var(--color-danger)";
        icon.className = "fa-solid fa-circle-xmark toast-icon";
        icon.style.color = "var(--color-danger)";
    }
    
    DOM.toast.classList.add("show");
    setTimeout(() => {
        DOM.toast.classList.remove("show");
    }, 2500);
}

// ==========================================================================
// INITIAL SETUP & RETRIEVAL
// ==========================================================================
async function testAIKey() {
    try {
        const apiKey = localStorage.getItem("gemini_api_key");
        const query = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
        const response = await fetch(`${API_BASE}/api/ai/test-key${query}`, {
            method: 'GET'
        });
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ Gemini API Key: OK');
        } else {
            console.warn('⚠️ Gemini API Key Issue:', result.message);
            showToast(result.message, 'error');
        }
    } catch (error) {
        console.error('Cannot test API key:', error);
    }
}

// Initialize Comparison Slider
function aiInitializeComparisonSlider() {
    const slider = document.getElementById('ai-comparison-slider');
    const container = document.getElementById('ai-comparison-container');
    const generatedImg = document.getElementById('ai-generated-image');
    
    if (!slider || !container) return;
    
    let isActive = false;
    
    function updateSliderPosition(e) {
        if (!isActive) return;
        
        const rect = container.getBoundingClientRect();
        let x = e.clientX - rect.left;
        
        // Touch support
        if (e.touches) {
            x = e.touches[0].clientX - rect.left;
        }
        
        // Clamp x to container bounds
        x = Math.max(0, Math.min(x, rect.width));
        
        // Update slider position and image clip
        const percentX = (x / rect.width) * 100;
        slider.style.left = percentX + '%';
        
        // Update generated image clip-path
        if (generatedImg) {
            generatedImg.style.clipPath = `inset(0 ${100 - percentX}% 0 0)`;
        }
    }
    
    // Mouse events
    slider.addEventListener('mousedown', () => {
        isActive = true;
    });
    
    document.addEventListener('mousemove', updateSliderPosition);
    
    document.addEventListener('mouseup', () => {
        isActive = false;
    });
    
    // Touch events
    slider.addEventListener('touchstart', () => {
        isActive = true;
    });
    
    document.addEventListener('touchmove', updateSliderPosition, { passive: true });
    
    document.addEventListener('touchend', () => {
        isActive = false;
    });
    
    // Click on container to move slider
    container.addEventListener('click', (e) => {
        if (e.target === slider || e.target.closest('.ai-slider-handle')) return;
        
        const rect = container.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentX = (x / rect.width) * 100;
        
        slider.style.left = percentX + '%';
        if (generatedImg) {
            generatedImg.style.clipPath = `inset(0 ${100 - percentX}% 0 0)`;
        }
    });
}

// ==========================================================================
// ZOOM FUNCTIONS FOR AI PREVIEW
// ==========================================================================
function aiApplyZoom() {
    const zoomLevel = state.aiColorTool.zoom;
    const previewImage = document.getElementById('ai-preview-image');
    const comparisonContainer = document.getElementById('ai-comparison-container');
    const originalImage = document.getElementById('ai-original-image');
    const generatedImage = document.getElementById('ai-generated-image');
    const viewport = document.querySelector('.ai-preview-viewport');
    
    // Apply zoom to preview image (single image mode)
    if (previewImage && previewImage.style.display !== 'none') {
        previewImage.style.transform = `scale(${zoomLevel})`;
    }
    
    // Apply zoom to comparison container and images
    if (comparisonContainer && comparisonContainer.style.display !== 'none') {
        comparisonContainer.style.transform = `scale(${zoomLevel})`;
        if (originalImage) originalImage.style.transform = `scale(1)`; // Already scaled by parent
        if (generatedImage) generatedImage.style.transform = `scale(1)`; // Already scaled by parent
    }
    
    // Update viewport overflow
    if (viewport) {
        if (zoomLevel > 1.0) {
            viewport.classList.add('zoom-active');
        } else {
            viewport.classList.remove('zoom-active');
        }
    }
    
    // Update zoom indicator
    aiUpdateZoomIndicator();
}

function aiUpdateZoomIndicator() {
    const viewport = document.querySelector('.ai-preview-viewport');
    if (!viewport) return;
    
    let indicator = document.getElementById('ai-zoom-indicator');
    
    // Create indicator if it doesn't exist
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'ai-zoom-indicator';
        indicator.className = 'zoom-level-indicator';
        viewport.appendChild(indicator);
    }
    
    const zoomPercent = Math.round(state.aiColorTool.zoom * 100);
    indicator.textContent = `${zoomPercent}%`;
    
    if (state.aiColorTool.zoom > 1.0) {
        indicator.classList.add('show');
    } else {
        indicator.classList.remove('show');
    }
}

function aiZoomIn() {
    if (state.aiColorTool.isProcessing) {
        showToast('AI đang xử lý, vui lòng chờ.', 'error');
        return;
    }
    
    const newZoom = Math.min(
        state.aiColorTool.zoom + 0.25,
        state.aiColorTool.maxZoom
    );
    
    if (newZoom > state.aiColorTool.maxZoom) {
        showToast(`Đã đạt mức phóng to tối đa (${state.aiColorTool.maxZoom * 100}%)`, 'success');
        return;
    }
    
    state.aiColorTool.zoom = newZoom;
    aiApplyZoom();
    console.log(`🔍 Zoom in: ${Math.round(newZoom * 100)}%`);
}

function aiZoomOut() {
    if (state.aiColorTool.isProcessing) {
        showToast('AI đang xử lý, vui lòng chờ.', 'error');
        return;
    }
    
    const newZoom = Math.max(
        state.aiColorTool.zoom - 0.25,
        state.aiColorTool.minZoom
    );
    
    if (newZoom < state.aiColorTool.minZoom) {
        showToast(`Đã đạt mức thu nhỏ tối thiểu (${state.aiColorTool.minZoom * 100}%)`, 'success');
        return;
    }
    
    state.aiColorTool.zoom = newZoom;
    aiApplyZoom();
    console.log(`🔍 Zoom out: ${Math.round(newZoom * 100)}%`);
}

function aiResetZoom() {
    state.aiColorTool.zoom = 1.0;
    aiApplyZoom();
    console.log('🔍 Zoom reset to 100%');
}

function aiDownloadImage() {
    const generatedImg = document.getElementById('ai-generated-image');
    const previewImg = document.getElementById('ai-preview-image');
    
    // Determine which image to download
    let imageSource = null;
    if (generatedImg && generatedImg.src && generatedImg.style.display !== 'none') {
        imageSource = generatedImg;
    } else if (previewImg && previewImg.src && previewImg.style.display !== 'none') {
        imageSource = previewImg;
    }
    
    if (!imageSource || !imageSource.src) {
        showToast('❌ Chưa có ảnh phối màu để tải xuống', 'error');
        console.warn('No image available for download');
        return;
    }
    
    try {
        // Create canvas from image
        const canvas = document.createElement('canvas');
        const img = new Image();
        
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext('2d');
            
            if (ctx) {
                ctx.drawImage(img, 0, 0);
                
                // Download as PNG
                canvas.toBlob(blob => {
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `phoi-mau-AI-${new Date().getTime()}.png`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(url);
                    
                    showToast('✅ Đã tải ảnh phối màu xuống máy', 'success');
                    console.log('✅ Image downloaded successfully');
                }, 'image/png');
            }
        };
        
        img.onerror = () => {
            console.error('Failed to load image for download');
            showToast('❌ Lỗi khi tải ảnh. Vui lòng thử lại.', 'error');
        };
        
        img.src = imageSource.src;
    } catch (error) {
        console.error('Download error:', error);
        showToast('❌ Lỗi khi tải ảnh: ' + error.message, 'error');
    }
}

async function initApp() {
    setupEventHandlers();
    
    // Test AI API key on startup
    await testAIKey();
    
    // Fetch initial setup data
    await Promise.all([
        fetchProjectTypes(),
        fetchBrands(),
        fetchColors(true),
        fetchCollections(true)
    ]);
    
    showToast("Hệ thống ArchiColor Pro đã sẵn sàng!");
}

// FETCH PROJECT TYPES
async function fetchProjectTypes() {
    try {
        const res = await fetch(`${API_BASE}/api/project-types`);
        const result = await res.json();
        if (result.success) {
            state.projectTypes = result.data;
            DOM.projectTypeFilter.innerHTML = '<option value="">Tất cả loại nhà</option>' + 
                state.projectTypes.map(t => `<option value="${t.id}">${t.name}</option>`).join("");
        }
    } catch (e) {
        console.error("Error fetching project types:", e);
    }
}

// FETCH PAINT BRANDS
async function fetchBrands() {
    try {
        const res = await fetch(`${API_BASE}/api/brands`);
        const result = await res.json();
        if (result.success) {
            state.brands = result.data;
            DOM.brandFilter.innerHTML = '<option value="">Tất cả hãng</option>' + 
                state.brands.map(b => `<option value="${b.id}">${b.name}</option>`).join("");
        }
    } catch (e) {
        console.error("Error fetching brands:", e);
    }
}

// FETCH HOUSE COLLECTIONS (TEMPLATES)
async function fetchCollections(reset = true) {
    if (state.isLoadingTemplates) return;
    state.isLoadingTemplates = true;
    
    if (reset) {
        state.pagination.templatesPage = 1;
        DOM.templatesGrid.innerHTML = `
            <div class="loading-spinner">
                <i class="fa-solid fa-circle-notch fa-spin"></i>
                <p>Đang tìm kiếm mẫu nhà...</p>
            </div>`;
    }
    
    try {
        const queryParams = new URLSearchParams({
            page: state.pagination.templatesPage,
            limit: 12
        });
        
        if (state.filters.projectTypeId) queryParams.append("project_type_id", state.filters.projectTypeId);
        if (state.filters.floors) queryParams.append("floors", state.filters.floors);
        if (state.filters.facades) queryParams.append("facades", state.filters.facades);
        if (state.filters.searchTemplates) queryParams.append("search", state.filters.searchTemplates);
        
        const res = await fetch(`${API_BASE}/api/collections?${queryParams.toString()}`);
        const result = await res.json();
        
        if (result.success) {
            const collections = result.data;
            const meta = result.meta;
            state.pagination.templatesHasMore = meta.has_more_pages;
            DOM.templatesCount.textContent = `${meta.total} mẫu`;
            // Update header count badge
            const countBadge = document.getElementById("templates-count");
            if (countBadge) countBadge.textContent = `${meta.total} mẫu`;
            
            if (reset) {
                state.collections = collections;
                DOM.templatesGrid.innerHTML = "";
            } else {
                state.collections.push(...collections);
            }
            
            if (state.collections.length === 0) {
                DOM.templatesGrid.innerHTML = `
                    <div class="no-templates-placeholder">
                        <i class="fa-solid fa-house-crack"></i>
                        <p>Không tìm thấy mẫu nhà phù hợp bộ lọc.</p>
                    </div>`;
            } else {
                renderTemplatesList(collections, reset);
            }
        }
    } catch (e) {
        console.error("Error fetching collections:", e);
        DOM.templatesGrid.innerHTML = `<p class="error">Không thể kết nối máy chủ.</p>`;
    } finally {
        state.isLoadingTemplates = false;
    }
}

// RENDER TEMPLATES TO GRID
function renderTemplatesList(newCollections, reset) {
    if (reset) DOM.templatesGrid.innerHTML = "";
    
    newCollections.forEach(col => {
        const item = document.createElement("div");
        item.className = "template-item";
        item.dataset.id = col.id;
        if (state.activeCollection && state.activeCollection.id === col.id) {
            item.classList.add("active");
        }
        
        const thumbUrl = col.thumbnail_url || "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=400&q=80";
        
        item.innerHTML = `
            <div class="template-thumbnail-wrapper">
                <img src="${thumbUrl}" alt="${col.name}" class="template-thumbnail" loading="lazy">
                <span class="template-badge">${col.project_type_name || 'Nhà mẫu'}</span>
            </div>
            <div class="template-info">
                <h4>Mẫu ${col.name}</h4>
                <div class="template-meta-info">
                    <span><i class="fa-solid fa-layer-group"></i> ${col.number_of_floors || 1} tầng</span>
                    <span><i class="fa-solid fa-border-all"></i> ${col.number_of_facades || 1} MT</span>
                </div>
            </div>
        `;
        
        item.addEventListener("click", () => selectCollection(col.id));
        DOM.templatesGrid.appendChild(item);
    });
}

// FETCH PAINT COLORS (WITH PAGINATION AND INFINITE SCROLL)
async function fetchColors(reset = true) {
    if (state.isLoadingColors) return;
    state.isLoadingColors = true;
    
    if (reset) {
        state.pagination.colorsPage = 1;
        state.pagination.colorsHasMore = true;
        DOM.colorsGrid.innerHTML = `
            <div class="loading-spinner">
                <i class="fa-solid fa-circle-notch fa-spin"></i>
                <p>Đang tải bảng màu...</p>
            </div>`;
        DOM.colorsGridContainer.scrollTop = 0;
    }
    
    DOM.colorsLoadMore.style.display = "flex";
    
    try {
        const queryParams = new URLSearchParams({
            page: state.pagination.colorsPage,
            limit: 24
        });
        
        if (state.filters.brandId) queryParams.append("brand_id", state.filters.brandId);
        if (state.filters.category) queryParams.append("category", state.filters.category);
        if (state.filters.searchColors) queryParams.append("search", state.filters.searchColors);
        
        const res = await fetch(`${API_BASE}/api/colors?${queryParams.toString()}`);
        const result = await res.json();
        
        if (result.success) {
            const colors = result.data;
            const meta = result.meta;
            state.pagination.colorsHasMore = meta.has_more_pages;
            // Update colors count indicator
            const countEl = document.getElementById("colors-count-indicator");
            if (countEl) countEl.textContent = `${meta.total.toLocaleString("vi-VN")} màu sơn trong thư viện`;
            
            if (reset) {
                state.colors = colors;
                DOM.colorsGrid.innerHTML = "";
            } else {
                state.colors.push(...colors);
            }
            
            if (state.colors.length === 0) {
                DOM.colorsGrid.innerHTML = `
                    <div class="no-templates-placeholder" style="grid-column: 1/-1;">
                        <i class="fa-solid fa-magnifying-glass-minus"></i>
                        <p>Không tìm thấy màu sắc phù hợp.</p>
                    </div>`;
            } else {
                renderColorsGrid(colors, reset);
                
                // Update color highlighting in case the newly loaded colors include the active layer's color
                if (!reset) {
                    updateColorHighlight();
                }
            }
            
            if (!state.pagination.colorsHasMore) {
                DOM.colorsLoadMore.style.display = "none";
            }
        }
    } catch (e) {
        console.error("Error fetching paint colors:", e);
        DOM.colorsGrid.innerHTML = `<p class="error" style="grid-column:1/-1;">Không thể tải bảng màu.</p>`;
    } finally {
        state.isLoadingColors = false;
    }
}

// RENDER PAINT COLORS TO PALETTE GRID
function renderColorsGrid(newColors, reset) {
    newColors.forEach(color => {
        const item = document.createElement("div");
        item.className = "color-item";
        item.dataset.hexCode = color.hex_code; // Store hex code for matching
        item.title = `${color.brand_name} - ${color.name} (finish: ${color.finish || 'Matt'})`;
        
        item.innerHTML = `
            <div class="color-bubble" style="background-color: ${color.hex_code};"></div>
            <span class="color-code">${color.paint_code}</span>
            <span class="color-name">${color.name}</span>
        `;
        
        item.addEventListener("click", (e) => {
            // Select and apply color
            applyColorToActiveLayer(color);
            
            // Highlight color bubble click micro-animation
            const bubble = item.querySelector(".color-bubble");
            bubble.style.transform = "scale(1.3)";
            setTimeout(() => bubble.style.transform = "none", 150);
        });
        
        DOM.colorsGrid.appendChild(item);
    });
    
    // Update color highlighting to show which color is applied to active layer
    updateColorHighlight();
}

// UPDATE COLOR ITEM HIGHLIGHTING BASED ON ACTIVE LAYER
function updateColorHighlight() {
    const activeLayerColor = state.activeLayer ? state.selectedColors[state.activeLayer.id] : null;
    
    // Get all color items in the grid
    const colorItems = DOM.colorsGrid.querySelectorAll(".color-item");
    
    // Clear all active highlights
    colorItems.forEach(item => {
        item.classList.remove("active");
    });
    
    // If there's no active layer or no color applied to it, nothing to highlight
    if (!activeLayerColor || !state.activeLayer) {
        return;
    }
    
    // Highlight the color matching the active layer's applied color
    colorItems.forEach(item => {
        // Get the hex code stored in the data attribute
        const itemHexCode = item.dataset.hexCode;
        
        if (!itemHexCode) return; // Skip if no hex code
        
        // Normalize hex codes for comparison (remove # and convert to uppercase)
        const normalizeHex = (hex) => {
            if (!hex) return "";
            return hex.replace(/^#/, "").toUpperCase();
        };
        
        // Check if this color item matches the applied color
        if (normalizeHex(itemHexCode) === normalizeHex(activeLayerColor)) {
            item.classList.add("active");
        }
    });
}

// ==========================================================================
// SELECTION & COMPOSITION LOGIC
// ==========================================================================
async function selectCollection(id, keepColors = false) {
    // Update active highlight class in templates grid cards
    document.querySelectorAll(".template-item").forEach(item => {
        if (item.dataset.id === id) item.classList.add("active");
        else item.classList.remove("active");
    });
    
    // Show workspace and hide placeholder
    const noProj = document.getElementById("no-project-placeholder");
    const editorGrid = document.getElementById("workspace-editor-grid");
    if (noProj) noProj.style.display = "none";
    if (editorGrid) editorGrid.style.display = "grid";
    
    // Switch navigation view to Phối màu 3D
    const tabVisualizer = document.getElementById("tab-visualizer");
    if (tabVisualizer && !tabVisualizer.classList.contains("active")) {
        tabVisualizer.click();
    }
    
    // Show visualizer loader
    DOM.canvasLoader.classList.add("active");
    
    try {
        const res = await fetch(`${API_BASE}/api/collections/${id}/layers`);
        const result = await res.json();
        
        if (result.success) {
            state.activeCollection = result.collection;
            state.activeCollection.layers = result.data;
            
            DOM.currentHouseName.textContent = `Mẫu Thiết Kế ${state.activeCollection.name}`;
            DOM.currentHouseDesc.textContent = state.activeCollection.description || "Hệ thống phối màu kiến trúc 3D với phân lớp ảnh WebP trong suốt";
            
            // Clear coloring states and image cache for new house
            if (!keepColors) {
                state.selectedColors = {};
                state.history = [];
                state.historyIndex = -1;
                updateHistoryControls();
            }
            state.layerImageCache = {};
            
            // Render layer list in right panel
            renderLayersPanel();
            
            // Preload all layer images to ensure smooth high-speed blending
            await preloadCollectionLayers(result.data);
            
            // Set initial selected layer (typically Wall or the first paintable layer)
            const paintableLayers = result.data.filter(l => l.layer_type !== "floor");
            if (paintableLayers.length > 0) {
                // Keep active layer if it matches one of the new layers
                const existingActive = paintableLayers.find(l => state.activeLayer && l.id === state.activeLayer.id);
                if (existingActive) {
                    selectActiveLayer(existingActive.id);
                } else {
                    selectActiveLayer(paintableLayers[0].id);
                }
            }
            
            // Re-render visualizer preview
            renderVisualizer();
        }
    } catch (e) {
        console.error("Error selecting collection:", e);
        showToast("Không thể tải các layer của mẫu nhà này", "danger");
    } finally {
        DOM.canvasLoader.classList.remove("active");
    }
}

// PRELOAD IMAGE LAYERS INTO FRONTEND CACHE
async function preloadCollectionLayers(layers) {
    const promises = layers.map(layer => {
        return new Promise((resolve) => {
            const img = new Image();
            img.crossOrigin = "anonymous"; // Try with CORS first
            img.src = layer.image_url;
            img.onload = () => {
                state.layerImageCache[layer.id] = img;
                resolve();
            };
            img.onerror = () => {
                // Fallback to normal loading without CORS restrictions if anonymous preflight fails
                const fallbackImg = new Image();
                fallbackImg.src = layer.image_url;
                fallbackImg.onload = () => {
                    state.layerImageCache[layer.id] = fallbackImg;
                    resolve();
                };
                fallbackImg.onerror = () => {
                    console.warn(`Could not preload layer image (fallback also failed): ${layer.image_url}`);
                    resolve();
                };
            };
        });
    });
    
    await Promise.all(promises);
}

// RENDER LAYERS PANEL IN RIGHT SIDEBAR
function renderLayersPanel() {
    if (!state.activeCollection || !state.activeCollection.layers) {
        DOM.layersList.innerHTML = `
            <div class="no-layers-placeholder">
                <i class="fa-solid fa-house-laptop"></i>
                <p>Vui lòng mở một mẫu nhà để hiển thị các phân vùng</p>
            </div>`;
        return;
    }
    
    const paintableLayers = state.activeCollection.layers.filter(l => l.layer_type !== "floor");
    
    if (paintableLayers.length === 0) {
        DOM.layersList.innerHTML = `<p class="no-layers-msg">Mẫu nhà này không chứa lớp có thể phối màu.</p>`;
        return;
    }
    
    DOM.layersList.innerHTML = paintableLayers.map(l => {
        const isCurrent = state.activeLayer && state.activeLayer.id === l.id;
        const appliedHex = state.selectedColors[l.id] || "#FFFFFF";
        const colorLabel = state.selectedColors[l.id] ? `Hex ${state.selectedColors[l.id]}` : "Chưa sơn";
        
        return `
            <div class="layer-item ${isCurrent ? 'active' : ''}" data-layer-id="${l.id}">
                <div class="layer-left-info">
                    <span class="layer-active-indicator"></span>
                    <span class="layer-name">${l.name}</span>
                </div>
                <div class="layer-right-info">
                    <span class="layer-color-code">${colorLabel}</span>
                    <div class="layer-color-preview" style="background-color: ${appliedHex};"></div>
                </div>
            </div>
        `;
    }).join("");
    
    // Add click listeners to layers
    DOM.layersList.querySelectorAll(".layer-item").forEach(item => {
        item.addEventListener("click", () => {
            selectActiveLayer(item.dataset.layerId);
        });
    });
}

// SELECT AN ACTIVE LAYER TO PAINT
function selectActiveLayer(layerId) {
    const layer = state.activeCollection.layers.find(l => l.id === layerId);
    if (!layer) return;
    
    state.activeLayer = layer;
    
    // Update active highlight border in right panel list
    DOM.layersList.querySelectorAll(".layer-item").forEach(item => {
        if (item.dataset.layerId === layerId) item.classList.add("active");
        else item.classList.remove("active");
    });
    
    // Update color highlighting to show which color is applied to the selected layer
    updateColorHighlight();
    
    showToast(`Đã chọn phân vùng: ${layer.name}. Hãy click chọn màu bên dưới!`);
}

// APPLY COLOR TO THE SELECTION
function applyColorToActiveLayer(color) {
    if (!state.activeCollection) {
        showToast("Vui lòng mở một mẫu nhà ở cột bên trái trước!", "danger");
        return;
    }
    if (!state.activeLayer) {
        showToast("Vui lòng chọn một phân vùng cần sơn ở cột bên phải!", "danger");
        return;
    }
    
    // Record current state in Undo history before making the modification
    saveToHistory();
    
    // Apply selected color
    state.selectedColors[state.activeLayer.id] = color.hex_code;
    
    // Toast alert
    showToast(`Đã sơn màu ${color.name} (${color.paint_code}) cho ${state.activeLayer.name}!`);
    
    // Update right sidebar list colors
    renderLayersPanel();
    
    // Update color highlighting in palette grid
    updateColorHighlight();
    
    // Trigger visualizer repaint
    renderVisualizer();
}

// ==========================================================================
// VISUALIZER RENDERING ENGINE (CANVAS & CSS BLEND MODES)
// ==========================================================================
function renderVisualizer() {
    if (!state.activeCollection || !state.activeCollection.layers) return;
    
    if (state.blendMethod === "canvas") {
        // Toggle view containers
        DOM.canvasWrapperReal.style.display = "flex";
        DOM.cssLayersWrapper.style.display = "none";
        DOM.cssLayersOriginalWrapper.style.display = "none";
        
        if (state.compareActive) {
            DOM.canvasWrapperOriginal.style.display = "flex";
            drawCanvasLayersOriginal();
        } else {
            DOM.canvasWrapperOriginal.style.display = "none";
        }
        
        drawCanvasLayers();
    } else {
        // Toggle view containers
        DOM.canvasWrapperReal.style.display = "none";
        DOM.canvasWrapperOriginal.style.display = "none";
        DOM.cssLayersWrapper.style.display = "flex";
        
        if (state.compareActive) {
            DOM.cssLayersOriginalWrapper.style.display = "flex";
            renderCssLayersOriginal();
        } else {
            DOM.cssLayersOriginalWrapper.style.display = "none";
        }
        
        renderCssLayers();
    }
}

// Draw uncolored original layers for comparison (AI Canvas mode)
function drawCanvasLayersOriginal() {
    const canvas = DOM.originalCanvas;
    const ctx = canvas.getContext("2d");
    
    const layers = state.activeCollection.layers;
    if (layers.length === 0) return;
    
    // Sort layers by z_index
    const sortedLayers = [...layers].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
    
    let canvasWidth = 1200;
    let canvasHeight = 750;
    
    for (let layer of sortedLayers) {
        const img = state.layerImageCache[layer.id];
        if (img && img.naturalWidth && img.naturalHeight) {
            canvasWidth = img.naturalWidth;
            canvasHeight = img.naturalHeight;
            break;
        }
    }
    
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    sortedLayers.forEach(layer => {
        const img = state.layerImageCache[layer.id];
        if (!img) return;
        
        ctx.globalAlpha = layer.opacity || 1.0;
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        ctx.globalAlpha = 1.0;
    });
}

// Render uncolored original layers stack for comparison (CSS Multiply mode)
function renderCssLayersOriginal() {
    const wrapper = DOM.cssLayersOriginalWrapper;
    wrapper.innerHTML = "";
    
    const layers = state.activeCollection.layers;
    const sortedLayers = [...layers].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
    
    sortedLayers.forEach(layer => {
        const container = document.createElement("div");
        container.className = "css-layer-container";
        container.style.zIndex = layer.z_index || layer.zIndex || 1;
        container.style.position = "absolute";
        container.style.width = "100%";
        container.style.height = "100%";
        container.style.display = "flex";
        container.style.alignItems = "center";
        container.style.justifyContent = "center";
        
        const img = document.createElement("img");
        img.className = "css-layer-img";
        img.style.position = "absolute";
        img.style.width = "100%";
        img.style.height = "100%";
        img.style.objectFit = "contain";
        img.style.pointerEvents = "none";
        img.src = layer.image_url;
        img.alt = layer.name;
        img.style.opacity = layer.opacity || 1.0;
        img.style.filter = "none"; // No recoloring filters!
        
        container.appendChild(img);
        wrapper.appendChild(container);
    });
}

// ==========================================================================
// DIRECT CANVAS CLICKING (CLICK-TO-SELECT LAYER)
// ==========================================================================
function handleVisualizerClick(e) {
    if (!state.activeCollection || !state.activeCollection.layers) return;
    
    // Choose coordinate anchor element based on active blend mode
    let activeEl = null;
    if (state.blendMethod === "canvas") {
        activeEl = DOM.mainCanvas;
    } else {
        // Select the top stacked image element inside CSS wrapper
        activeEl = DOM.cssLayersWrapper.querySelector(".css-layer-img");
    }
    
    if (!activeEl) return;
    
    const rect = activeEl.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const naturalWidth = activeEl.naturalWidth || activeEl.width;
    const naturalHeight = activeEl.naturalHeight || activeEl.height;
    
    if (!naturalWidth || !naturalHeight) return;
    
    // Map bounding boxes under 'object-fit: contain' to account for letterbox borders
    const elRatio = rect.width / rect.height;
    const imgRatio = naturalWidth / naturalHeight;
    
    let displayedWidth, displayedHeight, offsetX, offsetY;
    if (elRatio > imgRatio) {
        // Element is wider than image (horizontal borders)
        displayedHeight = rect.height;
        displayedWidth = rect.height * imgRatio;
        offsetX = (rect.width - displayedWidth) / 2;
        offsetY = 0;
    } else {
        // Element is taller than image (vertical borders)
        displayedWidth = rect.width;
        displayedHeight = rect.width / imgRatio;
        offsetX = 0;
        offsetY = (rect.height - displayedHeight) / 2;
    }
    
    // Compute pixel coordinates matching the original WebP asset resolution
    const imgX = ((x - offsetX) / displayedWidth) * naturalWidth;
    const imgY = ((y - offsetY) / displayedHeight) * naturalHeight;
    
    // Verify click is within actual transparent WebP boundaries
    if (imgX >= 0 && imgX < naturalWidth && imgY >= 0 && imgY < naturalHeight) {
        // Search paintable layers from TOP to BOTTOM (highest z_index first)
        const sortedLayers = [...state.activeCollection.layers].sort((a, b) => (b.z_index || 0) - (a.z_index || 0));
        
        for (let layer of sortedLayers) {
            if (layer.layer_type === "floor") continue; // Background layer is unpaintable
            
            const img = state.layerImageCache[layer.id];
            if (!img) continue;
            
            // Create a lightweight 1x1 offscreen canvas for extremely fast pixel alpha sampling
            const tempCanvas = document.createElement("canvas");
            tempCanvas.width = 1;
            tempCanvas.height = 1;
            const tempCtx = tempCanvas.getContext("2d");
            
            try {
                tempCtx.drawImage(img, Math.floor(imgX), Math.floor(imgY), 1, 1, 0, 0, 1, 1);
                const pixel = tempCtx.getImageData(0, 0, 1, 1).data;
                const alpha = pixel[3]; // Alpha alpha value (0-255)
                
                if (alpha > 10) { // Threshold for non-transparency (about 4% opacity)
                    selectActiveLayer(layer.id);
                    
                    // Smoothly scroll the layer list to highlight the selected item
                    const layerListItem = document.querySelector(`.layer-item[data-layer-id="${layer.id}"]`);
                    if (layerListItem) {
                        layerListItem.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    }
                    
                    showToast(`Đã chọn phân vùng: ${layer.name}`);
                    break;
                }
            } catch (err) {
                console.error("Alpha check failed (likely CORS on canvas source):", err);
            }
        }
    }
}

// ==========================================================================
// SAVED DESIGNS & SYSTEM PORTABILITY LOGIC
// ==========================================================================

// Setup Tab Switching in Left Sidebar
function setupSidebarTabs() {
    const tabAi = document.getElementById("tab-ai");
    const tabVisualizer = document.getElementById("tab-visualizer");
    const tabContentAi = document.getElementById("tab-content-ai");
    const tabContentVisualizer = document.getElementById("tab-content-visualizer");

    const tabs = [
        { btn: tabAi, content: tabContentAi },
        { btn: DOM.tabTemplates, content: DOM.tabContentTemplates },
        { btn: tabVisualizer, content: tabContentVisualizer },
        { btn: DOM.tabSaved, content: DOM.tabContentSaved }
    ];
    
    tabs.forEach(tab => {
        if (!tab.btn) return;
        tab.btn.addEventListener("click", () => {
            tabs.forEach(t => {
                if (t.btn) t.btn.classList.remove("active");
                if (t.content) t.content.classList.remove("active");
            });
            
            tab.btn.classList.add("active");
            if (tab.content) tab.content.classList.add("active");
            
            if (tab.btn === DOM.tabSaved) {
                fetchSavedDesigns();
            }
        });
    });
}

// Fetch list of designs from backend
async function fetchSavedDesigns() {
    try {
        DOM.savedDesignsList.innerHTML = `
            <div class="loading-spinner">
                <i class="fa-solid fa-circle-notch fa-spin"></i>
                <p>Đang tải thiết kế...</p>
            </div>
        `;
        
        const res = await fetch("/api/saved-designs");
        const data = await res.json();
        
        if (data.success) {
            state.savedDesigns = data.data;
            DOM.savedDesignsCount.textContent = `${state.savedDesigns.length} mẫu`;
            renderSavedDesignsList();
        } else {
            DOM.savedDesignsList.innerHTML = `<div class="no-designs-placeholder"><p>Không thể tải thiết kế.</p></div>`;
        }
    } catch (err) {
        console.error("fetchSavedDesigns error:", err);
        DOM.savedDesignsList.innerHTML = `<div class="no-designs-placeholder"><p>Lỗi kết nối máy chủ.</p></div>`;
    }
}

// Render designs card list in sidebar
function renderSavedDesignsList() {
    const container = DOM.savedDesignsList;
    container.innerHTML = "";
    
    if (state.savedDesigns.length === 0) {
        container.innerHTML = `
            <div class="no-designs-placeholder">
                <i class="fa-solid fa-folder-open"></i>
                <p>Chưa có thiết kế nào được lưu. Hãy phối màu và bấm "Lưu thiết kế"!</p>
            </div>
        `;
        return;
    }
    
    state.savedDesigns.forEach(design => {
        const item = document.createElement("div");
        item.className = "saved-design-item";
        
        // Color dots preview
        let colorsDots = "";
        Object.values(design.colors).forEach(hex => {
            colorsDots += `<span class="saved-design-color-dot" style="background-color: ${hex}"></span>`;
        });
        
        const dateStr = new Date(design.created_at).toLocaleDateString("vi-VN", {
            day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
        });
        
        item.innerHTML = `
            <div class="saved-design-header">
                <h4 class="saved-design-title" title="${design.name}">${design.name}</h4>
                <button class="delete-design-btn" data-id="${design.id}" title="Xóa thiết kế">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
            <div class="saved-design-meta">
                <span>Mẫu: ${design.collection_name || "Mẫu nhà"}</span>
                <span>${dateStr}</span>
            </div>
            <div class="saved-design-colors-preview">
                ${colorsDots}
            </div>
        `;
        
        // Restore design on click
        item.addEventListener("click", (e) => {
            if (e.target.closest(".delete-design-btn")) return;
            loadSavedDesign(design);
        });
        
        // Delete handler
        item.querySelector(".delete-design-btn").addEventListener("click", async (e) => {
            e.stopPropagation();
            if (confirm(`Bạn có chắc chắn muốn xóa thiết kế "${design.name}"?`)) {
                await deleteSavedDesign(design.id);
            }
        });
        
        container.appendChild(item);
    });
}

// Load a saved coloring project configuration
async function loadSavedDesign(design) {
    showToast(`Đang khôi phục thiết kế: ${design.name}...`);
    
    try {
        // Set selected colors state
        state.selectedColors = { ...design.colors };
        
        // Fetch new template collection, preserving colors state
        await selectCollection(design.collection_id, true);
        
        // Setup initial history
        state.history = [JSON.stringify(state.selectedColors)];
        state.historyIndex = 0;
        updateHistoryControls();
        
        // Force render UI elements
        renderLayersPanel();
        updateColorHighlight();
        renderVisualizer();
        // Return view to 3D visualizer
        const tabVisualizer = document.getElementById("tab-visualizer");
        if (tabVisualizer) tabVisualizer.click();
        
        showToast(`Khôi phục thành công "${design.name}"!`);
    } catch (err) {
        console.error("loadSavedDesign error:", err);
        showToast("Không thể khôi phục thiết kế.", "danger");
    }
}

// Delete saved design via API
async function deleteSavedDesign(id) {
    try {
        const res = await fetch(`/api/saved-designs/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (data.success) {
            showToast("Đã xóa thiết kế thành công!");
            fetchSavedDesigns();
        } else {
            showToast("Xóa thiết kế thất bại.", "danger");
        }
    } catch (err) {
        console.error("deleteSavedDesign error:", err);
        showToast("Không thể kết nối máy chủ để xóa.", "danger");
    }
}

// Setup Save Design Modal interactions
function setupSaveDesignModal() {
    DOM.btnSave.addEventListener("click", () => {
        if (!state.activeCollection) {
            showToast("Vui lòng mở một mẫu nhà để lưu thiết kế!", "danger");
            return;
        }
        DOM.saveDesignName.value = `Phương án ${state.activeCollection.name} - ${new Date().toLocaleDateString("vi-VN")}`;
        DOM.saveDesignModal.classList.add("show");
        DOM.saveDesignName.focus();
    });
    
    const closeModal = () => {
        DOM.saveDesignModal.classList.remove("show");
    };
    
    DOM.btnCloseModal.addEventListener("click", closeModal);
    DOM.btnCancelSave.addEventListener("click", closeModal);
    DOM.saveDesignModal.addEventListener("click", (e) => {
        if (e.target === DOM.saveDesignModal) closeModal();
    });
    
    DOM.btnConfirmSave.addEventListener("click", async () => {
        const name = DOM.saveDesignName.value.trim();
        if (!name) {
            showToast("Vui lòng nhập tên phương án thiết kế!", "danger");
            return;
        }
        
        const payload = {
            name: name,
            collection_id: state.activeCollection.id,
            colors: state.selectedColors
        };
        
        try {
            DOM.btnConfirmSave.disabled = true;
            DOM.btnConfirmSave.textContent = "Đang lưu...";
            
            const res = await fetch("/api/saved-designs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.success) {
                showToast(`Đã lưu thiết kế "${name}" thành công!`);
                closeModal();
                DOM.tabSaved.click(); // Open designs tab to show it
            } else {
                showToast("Lưu thiết kế thất bại.", "danger");
            }
        } catch (err) {
            console.error("Save design error:", err);
            showToast("Lỗi kết nối máy chủ.", "danger");
        } finally {
            DOM.btnConfirmSave.disabled = false;
            DOM.btnConfirmSave.textContent = "Lưu thiết kế";
        }
    });
}

// Setup Compare Mode Horizontal Slider toggles
function setupCompareMode() {
    DOM.btnCompare.addEventListener("click", () => {
        if (!state.activeCollection) {
            showToast("Vui lòng chọn mẫu nhà để so sánh!", "danger");
            return;
        }
        
        state.compareActive = !state.compareActive;
        DOM.btnCompare.classList.toggle("active", state.compareActive);
        DOM.visualizerContainer.classList.toggle("compare-active", state.compareActive);
        
        renderVisualizer();
        showToast(state.compareActive ? "Đã bật chế độ so sánh Trước/Sau!" : "Đã tắt chế độ so sánh Trước/Sau.");
    });
}

// 1. GPU-ACCELERATED HTML5 CANVAS DYNAMIC BLENDING
function drawCanvasLayers() {
    const canvas = DOM.mainCanvas;
    const ctx = canvas.getContext("2d");
    
    const layers = state.activeCollection.layers;
    if (layers.length === 0) return;
    
    // Sort layers by z_index to ensure correct rendering order
    const sortedLayers = [...layers].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
    
    // Set canvas base dimensions matching the first (lowest z_index) layer image
    let canvasWidth = 1200;
    let canvasHeight = 750;
    
    for (let layer of sortedLayers) {
        const img = state.layerImageCache[layer.id];
        if (img && img.naturalWidth && img.naturalHeight) {
            canvasWidth = img.naturalWidth;
            canvasHeight = img.naturalHeight;
            break;
        }
    }
    
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;
    
    // Clear whole canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw each layer in order (by z_index)
    sortedLayers.forEach(layer => {
        const img = state.layerImageCache[layer.id];
        if (!img) {
            console.warn(`Layer image not loaded: ${layer.name} (${layer.id})`);
            return;
        }
        
        const appliedHex = state.selectedColors[layer.id];
        
        // Only apply color to non-floor layers
        if (appliedHex && layer.layer_type !== "floor") {
            try {
                // Create intermediate offscreen canvases for color blending
                const colorCanvas = document.createElement("canvas");
                colorCanvas.width = canvas.width;
                colorCanvas.height = canvas.height;
                const cCtx = colorCanvas.getContext("2d");
                
                // Draw image and apply color using source-in composite
                cCtx.drawImage(img, 0, 0, canvas.width, canvas.height);
                cCtx.globalCompositeOperation = "source-in";
                cCtx.fillStyle = appliedHex;
                cCtx.fillRect(0, 0, canvas.width, canvas.height);
                
                // Create blending canvas
                const blendCanvas = document.createElement("canvas");
                blendCanvas.width = canvas.width;
                blendCanvas.height = canvas.height;
                const bCtx = blendCanvas.getContext("2d");
                
                // Draw colored mask
                bCtx.drawImage(colorCanvas, 0, 0);
                
                // Apply multiply blend to preserve shading details
                bCtx.globalCompositeOperation = "multiply";
                bCtx.drawImage(img, 0, 0, canvas.width, canvas.height);
                
                // Draw final blended result to main canvas
                ctx.globalAlpha = layer.opacity || 1.0;
                ctx.drawImage(blendCanvas, 0, 0);
                ctx.globalAlpha = 1.0;
                
            } catch (err) {
                console.error(`Canvas blending error for layer ${layer.name}:`, err);
                // Fallback: draw without color
                ctx.globalAlpha = layer.opacity || 1.0;
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                ctx.globalAlpha = 1.0;
            }
        } else {
            // Draw base layers (floor or uncolored) directly
            ctx.globalAlpha = layer.opacity || 1.0;
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            ctx.globalAlpha = 1.0;
        }
    });
}

// Helper to dynamically build or update SVG Filters in the document body
function updateSvgFilters() {
    let container = document.getElementById("svg-filters-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "svg-filters-container";
        container.style.display = "none";
        document.body.appendChild(container);
    }
    
    let svgHtml = '<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" style="position: absolute; width: 0; height: 0;">';
    
    if (state.activeCollection && state.activeCollection.layers) {
        state.activeCollection.layers.forEach(layer => {
            const appliedHex = state.selectedColors[layer.id];
            if (appliedHex && layer.layer_type !== "floor") {
                svgHtml += `
                    <filter id="recolor-filter-${layer.id}">
                        <feFlood flood-color="${appliedHex}" flood-opacity="1" result="flood" />
                        <feBlend mode="multiply" in="flood" in2="SourceGraphic" result="blend" />
                        <feComposite operator="in" in="blend" in2="SourceGraphic" />
                    </filter>
                `;
            }
        });
    }
    
    svgHtml += '</svg>';
    container.innerHTML = svgHtml;
}

// 2. STATE-OF-THE-ART SVG FILTER STACKED LAYERS (100% CORS-SAFE & GPU-ACCELERATED)
function renderCssLayers() {
    const wrapper = DOM.cssLayersWrapper;
    wrapper.innerHTML = "";
    
    // Generate/update the dynamic SVG filters for currently colored layers
    updateSvgFilters();
    
    const layers = state.activeCollection.layers;
    
    // Sort layers by z_index for correct rendering order
    const sortedLayers = [...layers].sort((a, b) => (a.z_index || 0) - (b.z_index || 0));
    
    sortedLayers.forEach(layer => {
        const container = document.createElement("div");
        container.className = "css-layer-container";
        container.style.zIndex = layer.z_index || layer.zIndex || 1;
        container.style.position = "absolute";
        container.style.width = "100%";
        container.style.height = "100%";
        container.style.display = "flex";
        container.style.alignItems = "center";
        container.style.justifyContent = "center";
        
        const img = document.createElement("img");
        img.className = "css-layer-img";
        img.style.position = "absolute";
        img.style.width = "100%";
        img.style.height = "100%";
        img.style.objectFit = "contain";
        img.style.pointerEvents = "none";
        img.src = layer.image_url;
        img.alt = layer.name;
        img.style.opacity = layer.opacity || 1.0;
        
        const appliedHex = state.selectedColors[layer.id];
        if (appliedHex && layer.layer_type !== "floor") {
            // Apply the custom dynamic SVG filter!
            img.style.filter = `url(#recolor-filter-${layer.id})`;
        } else {
            img.style.filter = "none";
        }
        
        container.appendChild(img);
        wrapper.appendChild(container);
    });
}

// ==========================================================================
// UNDO, REDO & RESET HISTORY CONTROLLERS
// ==========================================================================
function saveToHistory() {
    // Truncate future branch if user had undone operations and painted again
    state.history = state.history.slice(0, state.historyIndex + 1);
    
    // Save deeply cloned selected colors state
    state.history.push(JSON.stringify(state.selectedColors));
    state.historyIndex = state.history.length - 1;
    
    updateHistoryControls();
}

function handleUndo() {
    if (state.historyIndex >= 0) {
        if (state.historyIndex === state.history.length - 1) {
            // Save current final state before moving back
            state.history.push(JSON.stringify(state.selectedColors));
        }
        
        state.historyIndex--;
        
        if (state.historyIndex >= 0) {
            state.selectedColors = JSON.parse(state.history[state.historyIndex]);
        } else {
            state.selectedColors = {};
        }
        
        renderLayersPanel();
        updateColorHighlight();
        renderVisualizer();
        updateHistoryControls();
        showToast("Đã hoàn tác phối màu!");
    }
}

function handleRedo() {
    if (state.historyIndex < state.history.length - 1) {
        state.historyIndex++;
        state.selectedColors = JSON.parse(state.history[state.historyIndex]);
        
        renderLayersPanel();
        updateColorHighlight();
        renderVisualizer();
        updateHistoryControls();
        showToast("Đã tiến hành làm lại!");
    }
}

function handleReset() {
    if (!state.activeCollection) return;
    
    if (confirm("Bạn có chắc chắn muốn xóa toàn bộ màu sắc đã chọn và bắt đầu lại?")) {
        saveToHistory();
        state.selectedColors = {};
        renderLayersPanel();
        updateColorHighlight();
        renderVisualizer();
        showToast("Đã đặt lại toàn bộ màu sắc!");
    }
}

function updateHistoryControls() {
    DOM.btnUndo.disabled = state.historyIndex < 0;
    DOM.btnRedo.disabled = state.historyIndex >= state.history.length - 1;
}

// ==========================================================================
// IMAGE EXPORT HANDLER
// ==========================================================================
function exportImage() {
    if (!state.activeCollection) {
        showToast("Vui lòng mở một mẫu nhà để xuất ảnh!", "danger");
        return;
    }
    
    // Ensure drawing is fully updated on Canvas
    drawCanvasLayers();
    
    try {
        const link = document.createElement("a");
        link.download = `phoi-mau-archi-mẫu-${state.activeCollection.name}.png`;
        link.href = DOM.mainCanvas.toDataURL("image/png");
        link.click();
        showToast("Đang tải xuống ảnh phối màu...");
    } catch (e) {
        console.error("Export failed:", e);
        showToast("Không thể xuất ảnh do giới hạn bảo mật tài nguyên bên ngoài (CORS)", "danger");
    }
}

// ==========================================================================
// WORKSPACE FILTER HANDLERS & SCROLL EVENTS
// ==========================================================================
function setupEventHandlers() {
    // 0. AI COLOR TOOL EVENT HANDLERS
    const aiFileInput = document.getElementById("ai-file-input");
    if (aiFileInput) {
        aiFileInput.addEventListener("change", (e) => {
            if (state.aiColorTool.isProcessing) return;
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = async (event) => {
                    const compressedImage = await aiCompressImageDataUrl(event.target.result);
                    state.aiColorTool.uploadedImage = compressedImage;
                    window.globalDetectedAreas = [];
                    state.aiColorTool.detectedAreasRequestKey = null;
                    state.aiColorTool.imageId = null;
                    state.aiColorTool.lastClick = null;
                    state.aiColorTool.areaClicks = {};
                    state.aiColorTool.zoom = 1.0; // Reset zoom on new image
                    
                    // Reset comparison slider
                    const comparisonContainer = document.getElementById('ai-comparison-container');
                    const previewImage = document.getElementById('ai-preview-image');
                    const previewPlaceholder = document.getElementById('ai-preview-placeholder');
                    const previewControls = document.getElementById('ai-preview-controls');
                    
                    if (comparisonContainer) comparisonContainer.style.display = 'none';
                    if (previewImage) previewImage.style.display = 'none';
                    
                    // Show original image temporarily
                    if (previewImage) {
                        previewImage.src = compressedImage;
                        previewImage.style.display = 'block';
                        previewImage.style.transform = 'scale(1)'; // Reset transform
                    }
                    
                    if (previewPlaceholder) previewPlaceholder.style.display = 'none';
                    if (previewControls) previewControls.style.display = 'flex';
                    
                    document.getElementById('ai-preview-status').textContent = 'Ảnh đã tải lên thành công. Chọn loại công trình.';
                    aiGoToStep(2);
                    showToast('Ảnh đã tải lên thành công!', 'success');
                    document.getElementById('ai-preview-status').textContent = 'Anh da tai len. Chon noi that/ngoai that, chon mau tung chi tiet roi bam tao anh AI.';
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // Add drag-drop support for upload area
    const uploadArea = document.querySelector(".upload-area");
    if (uploadArea) {
        uploadArea.addEventListener("click", (e) => {
            if (state.aiColorTool.isProcessing) {
                e.preventDefault();
                e.stopPropagation();
                showToast('AI đang xử lý, vui lòng chờ kết quả.', 'error');
            }
        }, true);
        uploadArea.addEventListener("dragover", (e) => {
            if (state.aiColorTool.isProcessing) {
                e.preventDefault();
                return;
            }
            e.preventDefault();
            uploadArea.style.borderColor = "var(--color-primary)";
            uploadArea.style.background = "rgba(67, 82, 165, 0.05)";
        });
        uploadArea.addEventListener("dragleave", () => {
            uploadArea.style.borderColor = "#e5e7eb";
            uploadArea.style.background = "#fafbfc";
        });
        uploadArea.addEventListener("drop", (e) => {
            if (state.aiColorTool.isProcessing) {
                e.preventDefault();
                return;
            }
            e.preventDefault();
            uploadArea.style.borderColor = "#e5e7eb";
            uploadArea.style.background = "#fafbfc";
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                aiFileInput.files = files;
                aiFileInput.dispatchEvent(new Event('change'));
            }
        });
    }

    ['ai-preview-image', 'ai-generated-image', 'ai-original-image'].forEach((id) => {
        const imageEl = document.getElementById(id);
        if (imageEl) {
            imageEl.style.cursor = 'default';
        }
    });

    // Color palette items click handler
    const colorPaletteItems = document.querySelectorAll(".color-palette-item");
    colorPaletteItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const hexColor = window.getComputedStyle(item).backgroundColor;
            const colorCode = item.getAttribute("title");
            
            // Remove selected from all
            colorPaletteItems.forEach(ci => ci.classList.remove("selected"));
            // Add selected to clicked
            item.classList.add("selected");
            
            aiSelectColor(hexColor);
            showToast(`Đã chọn màu ${colorCode}`, 'success');
        });
    });

    // 1. TEMPLATE FILTERS — update state before refetch
    DOM.projectTypeFilter.addEventListener("change", (e) => {
        state.filters.projectTypeId = e.target.value;
        fetchCollections(true);
    });
    DOM.floorsFilter.addEventListener("change", (e) => {
        state.filters.floors = e.target.value;
        fetchCollections(true);
    });
    DOM.facadesFilter.addEventListener("change", (e) => {
        state.filters.facades = e.target.value;
        fetchCollections(true);
    });
    
    // Debounced templates keyword search
    DOM.searchTemplates.addEventListener("input", debounce((e) => {
        state.filters.searchTemplates = e.target.value;
        fetchCollections(true);
    }, 300));
    
    // Infinite Scroll — watch the scrollable tab content wrapper
    const tabTemplatesContent = document.getElementById("tab-content-templates");
    if (tabTemplatesContent) {
        tabTemplatesContent.addEventListener("scroll", () => {
            if (state.isLoadingTemplates || !state.pagination.templatesHasMore) return;
            const { scrollTop, clientHeight, scrollHeight } = tabTemplatesContent;
            if (scrollTop + clientHeight >= scrollHeight - 80) {
                state.pagination.templatesPage++;
                fetchCollections(false);
            }
        });
    }

    // 2. RIGHT SIDEBAR COLOR PALETTES
    DOM.brandFilter.addEventListener("change", (e) => {
        state.filters.brandId = e.target.value;
        fetchColors(true);
    });
    
    DOM.searchColors.addEventListener("input", debounce((e) => {
        state.filters.searchColors = e.target.value;
        fetchColors(true);
    }, 300));
    
    // Quick filter chips for colors
    DOM.colorCategoryChips.forEach(chip => {
        chip.addEventListener("click", () => {
            DOM.colorCategoryChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            
            state.filters.category = chip.dataset.cat;
            fetchColors(true);
        });
    });
    
    // Infinite Scroll on colors scroll bottom
    DOM.colorsGridContainer.addEventListener("scroll", () => {
        if (state.isLoadingColors || !state.pagination.colorsHasMore) return;
        
        const { scrollTop, clientHeight, scrollHeight } = DOM.colorsGridContainer;
        if (scrollTop + clientHeight >= scrollHeight - 40) {
            state.pagination.colorsPage++;
            fetchColors(false);
        }
    });

    // 3. CANVAS BLEND MODE TOGGLING
    DOM.blendMethodToggle.addEventListener("change", (e) => {
        state.blendMethod = e.target.checked ? "css" : "canvas";
        
        DOM.modeCanvasSpan.classList.toggle("active", !e.target.checked);
        DOM.modeCssSpan.classList.toggle("active", e.target.checked);
        
        renderVisualizer();
        showToast(`Đã chuyển sang chế độ hòa trộn: ${state.blendMethod === "canvas" ? "AI Canvas" : "CSS Multiply"}`);
    });

    // 4. HEADER ACTION CONTROLS
    DOM.btnUndo.addEventListener("click", handleUndo);
    DOM.btnRedo.addEventListener("click", handleRedo);
    DOM.btnReset.addEventListener("click", handleReset);
    DOM.btnExport.addEventListener("click", exportImage);
    
    // 5. COMPARE MODE
    setupCompareMode();
    
    // 6. SAVED DESIGNS TABS & MODALS
    setupSidebarTabs();
    setupSaveDesignModal();
    
    // 7. DIRECT CANVAS CLICK SELECTION
    DOM.visualizerContainer.addEventListener("click", handleVisualizerClick);
    
    // 7.5. ZOOM CONTROLS FOR AI PREVIEW
    const zoomInBtn = document.querySelector('.ai-preview-controls .control-icon-btn:nth-child(1)');
    const zoomOutBtn = document.querySelector('.ai-preview-controls .control-icon-btn:nth-child(2)');
    
    if (zoomInBtn) {
        zoomInBtn.textContent = '🔍+';
        zoomInBtn.title = 'Phóng to (Zoom In)';
        zoomInBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            aiZoomIn();
        });
    }
    
    if (zoomOutBtn) {
        zoomOutBtn.textContent = '🔍−';
        zoomOutBtn.title = 'Thu nhỏ (Zoom Out)';
        zoomOutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            aiZoomOut();
        });
    }
    
    // Add keyboard shortcuts for zoom
    document.addEventListener('keydown', (e) => {
        const previewViewport = document.querySelector('.ai-preview-viewport');
        const isPreviewVisible = previewViewport && 
                                (document.getElementById('ai-preview-image')?.style.display !== 'none' ||
                                 document.getElementById('ai-comparison-container')?.style.display !== 'none');
        
        if (!isPreviewVisible) return;
        
        // Ctrl/Cmd + Plus = Zoom In
        if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '=')) {
            e.preventDefault();
            aiZoomIn();
        }
        
        // Ctrl/Cmd + Minus = Zoom Out
        if ((e.ctrlKey || e.metaKey) && e.key === '-') {
            e.preventDefault();
            aiZoomOut();
        }
        
        // Ctrl/Cmd + 0 = Reset Zoom
        if ((e.ctrlKey || e.metaKey) && e.key === '0') {
            e.preventDefault();
            aiResetZoom();
        }
    });
    
    // 8. LOAD API KEY FROM STORAGE
    loadAPIKey();
}

// ==================== API KEY MODAL FUNCTIONS ====================

/**
 * Open the API Key modal dialog
 */
function openAPIKeyModal() {
    const modal = document.getElementById("apiKeyModal");
    if (!modal) return;
    
    // Load existing key from storage
    const savedKey = localStorage.getItem("gemini_api_key");
    const input = document.getElementById("apiKeyInput");
    
    if (input && savedKey) {
        input.value = savedKey;
    }
    
    // Add show class to make modal visible
    modal.classList.add("show");
    input?.focus();
}

/**
 * Close the API Key modal dialog
 */
function closeAPIKeyModal() {
    const modal = document.getElementById("apiKeyModal");
    if (modal) {
        // Remove show class to hide modal
        modal.classList.remove("show");
    }
    clearAPIKeyStatus();
}

/**
 * Toggle password visibility in API Key input
 */
function togglePasswordVisibility() {
    const input = document.getElementById("apiKeyInput");
    const btn = document.querySelector(".toggle-password-btn");
    
    if (!input || !btn) return;
    
    if (input.type === "password") {
        input.type = "text";
        btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
    } else {
        input.type = "password";
        btn.innerHTML = '<i class="fa-solid fa-eye"></i>';
    }
}

/**
 * Test the Gemini API key
 */
async function testAPIKey() {
    const input = document.getElementById("apiKeyInput");

    const testBtn = document.getElementById("testKeyBtn");
    if (testBtn) testBtn.disabled = true;
    
    showAPIKeyStatus("Đang kiểm tra API Key...", "loading");
    
    try {
        const apiKey = input?.value.trim() || localStorage.getItem("gemini_api_key") || "";
        const query = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
        const response = await fetch(`${API_BASE}/api/ai/test-key${query}`, {
            method: "GET"
        });
        
        if (response.ok) {
            showAPIKeyStatus("✓ API Key hợp lệ! Bạn có thể sử dụng tính năng Phối Màu AI.", "success");
        } else {
            const data = await response.json();
            showAPIKeyStatus(`✗ ${data.error || "API Key không hợp lệ"}`, "error");
        }
    } catch (error) {
        console.error("Error testing API key:", error);
        showAPIKeyStatus("✗ Lỗi kết nối. Vui lòng thử lại.", "error");
    } finally {
        if (testBtn) testBtn.disabled = false;
    }
}

/**
 * Save the API Key to localStorage
 */
async function saveAPIKey() {
    const input = document.getElementById("apiKeyInput");
    if (!input || !input.value.trim()) {
        showAPIKeyStatus("Vui lòng nhập API Key", "warning");
        return;
    }
    
    // Save to localStorage
    localStorage.setItem("gemini_api_key", input.value.trim());
    
    showAPIKeyStatus("✓ API Key đã được lưu thành công!", "success");
    
    // Close modal after 2 seconds
    setTimeout(() => {
        closeAPIKeyModal();
    }, 2000);
}

/**
 * Load API Key from localStorage and use it in fetch requests
 */
function loadAPIKey() {
    const apiKey = localStorage.getItem("gemini_api_key");
    // Store in state for use in API calls
    if (apiKey) {
        state.apiKey = apiKey;
    }
}

/**
 * Show status message in modal
 */
function showAPIKeyStatus(message, type = "info") {
    const statusEl = document.getElementById("apiKeyStatus");
    if (!statusEl) return;
    
    // Remove all status classes
    statusEl.classList.remove("success", "error", "warning", "loading");
    
    // Add the appropriate class
    statusEl.classList.add(type);
    
    // Set message with icon
    let icon = "ℹ️";
    if (type === "success") icon = "✓";
    else if (type === "error") icon = "✗";
    else if (type === "warning") icon = "⚠️";
    else if (type === "loading") icon = '<i class="fa-solid fa-spinner fa-spin"></i>';
    
    statusEl.innerHTML = `${icon} ${message}`;
}

/**
 * Clear API Key status message
 */
function clearAPIKeyStatus() {
    const statusEl = document.getElementById("apiKeyStatus");
    if (statusEl) {
        statusEl.innerHTML = "";
        statusEl.classList.remove("success", "error", "warning", "loading");
    }
}

/**
 * Enhanced fetch wrapper that includes API key if available
 */
async function fetchWithAPIKey(url, options = {}) {
    const apiKey = localStorage.getItem("gemini_api_key");
    
    // Prepare request body
    const body = options.body ? JSON.parse(options.body) : {};
    
    // Add API key to request if available
    if (apiKey && url.includes("/api/ai/")) {
        body.api_key = apiKey;
    }
    
    // Update options
    options.body = JSON.stringify(body);
    
    return fetch(url, options);
}

// Start visualizer on browser load
window.addEventListener("DOMContentLoaded", initApp);
