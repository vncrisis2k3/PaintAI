// ==========================================================================
// AI PAINT VISUALIZER SPA (React 19 & Tailwind CSS)
// ==========================================================================

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'https://esm.sh/react@19';
import ReactDOM from 'https://esm.sh/react-dom@19/client';

// ==========================================================================
// PHẦN 2: LOGIC PROMPT AI HỆ THỐNG (SYSTEM PROMPT) & GEMINI API INTEGRATION
// ==========================================================================
const SYSTEM_PROMPT = `
You are an expert architectural color consultant and AI vision engineer.
Your task is to analyze the provided image of a building and recommend a highly aesthetic, realistic paint color scheme.
You must perform the following:
1. Semantic Segmentation analysis: Identify the main walls, columns/pillars, cornice/trim, and roof outlines. You must preserve the window glass, doors, vegetation, sky, and original ambient lighting untouched.
2. Advanced Texture Mapping guidance: Blend the target color paint code with the existing 3D shadows, light sources, and surface textures of the building. Maintain original roughness and specular highlights.
3. Determine:
   - The architectural style of the building (e.g., Modern Minimalist, Neoclassical, Nordic, Classical, Mid-century Modern).
   - A primary paint color recommendation (paint name, brand, hex code).
   - An accent paint color recommendation (paint name, brand, hex code).
   - Detailed design reasoning explaining why this palette fits the architectural style and enhances curb appeal.

Your output must be a valid JSON object matching this schema:
{
  "architecturalStyle": "string",
  "primaryPaint": {
    "name": "string",
    "brand": "string",
    "hex": "string",
    "paintCode": "string"
  },
  "accentPaint": {
    "name": "string",
    "brand": "string",
    "hex": "string",
    "paintCode": "string"
  },
  "designReasoning": "string"
}
`;

// ==========================================================================
// FRONTEND COMPONENT & CORE LOGIC
// ==========================================================================

const SAMPLE_IMAGES = [
    {
        id: 'sample-1',
        name: 'Biệt thự hiện đại',
        src: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=900&q=85',
        seeds: {
            wall: [{ x: 300, y: 350 }, { x: 500, y: 350 }],
            accent: [{ x: 750, y: 350 }],
            roof: [{ x: 450, y: 150 }],
            trim: [{ x: 600, y: 450 }]
        }
    },
    {
        id: 'sample-2',
        name: 'Nhà phố 3 tầng',
        src: 'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=900&q=85',
        seeds: {
            wall: [{ x: 400, y: 400 }],
            accent: [{ x: 500, y: 250 }],
            roof: [{ x: 400, y: 100 }],
            trim: [{ x: 300, y: 200 }]
        }
    },
    {
        id: 'sample-3',
        name: 'Nhà vườn mái thái',
        src: 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=900&q=85',
        seeds: {
            wall: [{ x: 350, y: 450 }],
            accent: [{ x: 580, y: 400 }],
            roof: [{ x: 350, y: 250 }],
            trim: [{ x: 450, y: 430 }]
        }
    },
    {
        id: 'sample-4',
        name: 'Phòng khách Bắc Âu',
        src: 'https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=900&q=85',
        seeds: {
            wall: [{ x: 200, y: 300 }],
            accent: [{ x: 500, y: 300 }],
            roof: [{ x: 400, y: 100 }], // maps to ceiling
            trim: [{ x: 100, y: 450 }]
        }
    }
];

const PALETTE_GROUPS = {
    modern: {
        name: 'Hiện đại',
        colors: [
            { code: 'OW-101', name: 'Trắng tinh khôi', hex: '#F4F5F6' },
            { code: 'GY-502', name: 'Xám ghi hiện đại', hex: '#6E7A8A' },
            { code: 'BK-900', name: 'Đen Charcoal', hex: '#2D3238' },
            { code: 'BL-303', name: 'Xanh Teal dịu', hex: '#3C6D7D' },
            { code: 'GN-402', name: 'Sage xanh nhạt', hex: '#8C9D8E' },
            { code: 'BL-506', name: 'Xanh dương thép', hex: '#4F6B82' }
        ]
    },
    neoclassical: {
        name: 'Tân cổ điển',
        colors: [
            { code: 'CR-201', name: 'Kem Cát Ấm', hex: '#F2E7D5' },
            { code: 'GD-802', name: 'Vàng Cổ Điển', hex: '#CBB285' },
            { code: 'OW-202', name: 'Trắng Sữa Hoàng Gia', hex: '#FAF6EE' },
            { code: 'RD-901', name: 'Đỏ Bordeaux', hex: '#7D2E38' },
            { code: 'GN-808', name: 'Xanh Ngọc Lục Bảo', hex: '#2E5A44' },
            { code: 'BR-403', name: 'Nâu Warm Taupe', hex: '#8A7B6E' }
        ]
    },
    nordic: {
        name: 'Bắc Âu',
        colors: [
            { code: 'WH-001', name: 'Trắng Tuyết', hex: '#FFFFFF' },
            { code: 'GY-102', name: 'Xám Sương Mù', hex: '#D3D6DB' },
            { code: 'BL-101', name: 'Xanh Trời Nhạt', hex: '#A5C4D4' },
            { code: 'BR-202', name: 'Gỗ Sồi Ấm', hex: '#C1A78B' },
            { code: 'GN-301', name: 'Xanh Lá Thông', hex: '#546E65' },
            { code: 'PK-102', name: 'Hồng Phấn Soft Rose', hex: '#E8C8C5' }
        ]
    },
    fengshui: {
        name: 'Phong thủy',
        colors: [
            { code: 'FS-KIM', name: 'Trắng Bản Mệnh (Kim)', hex: '#FAF9F6' },
            { code: 'FS-MOC', name: 'Xanh Bản Mệnh (Mộc)', hex: '#228B22' },
            { code: 'FS-THUY', name: 'Xanh Biển (Thủy)', hex: '#0077BE' },
            { code: 'FS-HOA', name: 'Đỏ Bản Mệnh (Hỏa)', hex: '#FF7F50' },
            { code: 'FS-THO', name: 'Nâu Đất (Thổ)', hex: '#B87333' },
            { code: 'FS-HOANG', name: 'Vàng Hoàng Thổ (Thổ)', hex: '#D4AF37' }
        ]
    }
};

const REGION_LABELS = {
    wall: { name: 'Tường chính', icon: '🧱' },
    accent: { name: 'Điểm nhấn', icon: '🎨' },
    roof: { name: 'Mái nhà / Trần', icon: '🏠' },
    trim: { name: 'Phào chỉ / Viền', icon: '🏛️' }
};

function App() {
    // PaintAI 3-step wizard state
    const [step, setStep] = useState(1); // 1: choose type, 2: upload, 3: editor
    const [buildingType, setBuildingType] = useState(null); // 'interior' | 'exterior'
    
    const [view, setView] = useState('upload'); // kept for compatibility
    const [aiMode, setAiMode] = useState('auto');
    const [selectedTheme, setSelectedTheme] = useState('modern');
    const [activeRegion, setActiveRegion] = useState('wall');
    const [selectedColor, setSelectedColor] = useState(PALETTE_GROUPS.modern.colors[0]);
    const [opacitySlider, setOpacitySlider] = useState(90);
    const [dayNight, setDayNight] = useState('day');
    const [sliderPos, setSliderPos] = useState(50);
    const [isDragging, setIsDragging] = useState(false);
    const [tolerance, setTolerance] = useState(30);

    // Core Image & Processing states
    const [imageSrc, setImageSrc] = useState(null);
    const [imgElement, setImgElement] = useState(null);
    const [masks, setMasks] = useState({ wall: null, accent: null, roof: null, trim: null });
    const [appliedColors, setAppliedColors] = useState({ wall: '#F4F5F6', accent: '#6E7A8A', roof: '#2D3238', trim: '#FFFFFF' });
    
    // History (Undo / Redo)
    const [history, setHistory] = useState([]);
    const [historyIndex, setHistoryIndex] = useState(-1);

    // API & AI states
    const [apiKey, setApiKey] = useState(localStorage.getItem('gemini_api_key') || '');
    const [showApiKeyModal, setShowApiKeyModal] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [aiReport, setAiReport] = useState(null);

    // Refs
    const canvasRef = useRef(null);
    const fileInputRef = useRef(null);
    const sliderContainerRef = useRef(null);

    // Load API key from localstorage
    useEffect(() => {
        if (apiKey) {
            localStorage.setItem('gemini_api_key', apiKey);
        }
    }, [apiKey]);

    // Setup Image element when source changes
    useEffect(() => {
        if (!imageSrc) return;
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            setImgElement(img);
            // Reset masks
            setMasks({ wall: null, accent: null, roof: null, trim: null });
            setHistory([]);
            setHistoryIndex(-1);
            setView('editor');
            setStep(3);
        };
        img.src = imageSrc;
    }, [imageSrc]);

    // Save current color configuration to history
    const saveHistory = useCallback((colors, currentMasks) => {
        const nextHistory = history.slice(0, historyIndex + 1);
        const stateSnapshot = {
            colors: { ...colors },
            masks: { ...currentMasks }
        };
        setHistory([...nextHistory, JSON.stringify(stateSnapshot)]);
        setHistoryIndex(nextHistory.length);
    }, [history, historyIndex]);

    // Undo & Redo handlers
    const handleUndo = () => {
        if (historyIndex > 0) {
            const prevIdx = historyIndex - 1;
            const prev = JSON.parse(history[prevIdx]);
            setAppliedColors(prev.colors);
            setMasks(prev.masks);
            setHistoryIndex(prevIdx);
        } else if (historyIndex === 0) {
            setHistoryIndex(-1);
            setAppliedColors({ wall: null, accent: null, roof: null, trim: null });
            setMasks({ wall: null, accent: null, roof: null, trim: null });
        }
    };

    const handleRedo = () => {
        if (historyIndex < history.length - 1) {
            const nextIdx = historyIndex + 1;
            const next = JSON.parse(history[nextIdx]);
            setAppliedColors(next.colors);
            setMasks(next.masks);
            setHistoryIndex(nextIdx);
        }
    };

    const handleReset = () => {
        setAppliedColors({ wall: null, accent: null, roof: null, trim: null });
        setMasks({ wall: null, accent: null, roof: null, trim: null });
        setHistory([]);
        setHistoryIndex(-1);
    };

    // Redraw Canvas whenever rendering states change
    useEffect(() => {
        if (!imgElement || !canvasRef.current) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        
        // Set canvas sizes matching original aspect ratio
        const maxW = 960;
        const maxH = 640;
        let w = imgElement.naturalWidth || imgElement.width || 960;
        let h = imgElement.naturalHeight || imgElement.height || 640;
        if (w > maxW) { h = Math.round(h * maxW / w); w = maxW; }
        if (h > maxH) { w = Math.round(w * maxH / h); h = maxH; }
        canvas.width = w;
        canvas.height = h;

        // Draw original background
        ctx.drawImage(imgElement, 0, 0, w, h);

        // Create temporary canvas for recoloring
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        const tCtx = tempCanvas.getContext('2d');
        tCtx.drawImage(imgElement, 0, 0, w, h);

        // Paint each mask region
        let hasAnyAppliedColor = false;
        Object.keys(appliedColors).forEach(regionId => {
            const mask = masks[regionId];
            const colorHex = appliedColors[regionId];
            if (mask && colorHex) {
                hasAnyAppliedColor = true;
                applyColorMask(tCtx, mask, colorHex, opacitySlider / 100);
            }
        });

        // Night mode filters
        if (dayNight === 'night') {
            applyNightFilter(tCtx, w, h);
        }

        // Split screen rendering
        const splitX = w * (sliderPos / 100);

        // Draw split screen boundary
        ctx.save();
        ctx.beginPath();
        ctx.rect(splitX, 0, w - splitX, h);
        ctx.clip();
        ctx.drawImage(tempCanvas, 0, 0);
        ctx.restore();

        // Draw slider line divider
        ctx.save();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2.5;
        ctx.shadowColor = 'rgba(0, 0, 0, 0.4)';
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.moveTo(splitX, 0);
        ctx.lineTo(splitX, h);
        ctx.stroke();

        // Split slider circle knob
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(splitX, h / 2, 18, 0, Math.PI * 2);
        ctx.fill();

        // Arrows text inside knob
        ctx.fillStyle = '#4f46e5';
        ctx.font = 'bold 15px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('↔', splitX, h / 2);
        ctx.restore();

    }, [imgElement, masks, appliedColors, opacitySlider, dayNight, sliderPos]);

    // Helper functions for blending and masks
    const hexToRgb = (hex) => {
        const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : { r: 255, g: 255, b: 255 };
    };

    const applyColorMask = (ctx, mask, hex, opacity) => {
        const w = ctx.canvas.width;
        const h = ctx.canvas.height;
        const imgData = ctx.getImageData(0, 0, w, h);
        const d = imgData.data;
        const { r, g, b } = hexToRgb(hex);

        // Blend colors inside mask boundaries
        for (let i = 0; i < mask.length; i++) {
            if (mask[i] > 0) {
                const idx = i * 4;
                const origR = d[idx];
                const origG = d[idx+1];
                const origB = d[idx+2];

                // Multiply blending mode: (original * blendColor) / 255
                const blendR = (origR * r) / 255;
                const blendG = (origG * g) / 255;
                const blendB = (origB * b) / 255;

                // Blend with opacity
                d[idx]   = Math.round(origR * (1 - opacity) + blendR * opacity);
                d[idx+1] = Math.round(origG * (1 - opacity) + blendG * opacity);
                d[idx+2] = Math.round(origB * (1 - opacity) + blendB * opacity);
            }
        }
        ctx.putImageData(imgData, 0, 0);
    };

    const applyNightFilter = (ctx, w, h) => {
        const imgData = ctx.getImageData(0, 0, w, h);
        const d = imgData.data;

        // Reduce overall brightness, add moonlight/ambient night cool blue tones
        for (let i = 0; i < d.length; i += 4) {
            d[i]   = Math.round(d[i] * 0.40);       // Red down
            d[i+1] = Math.round(d[i+1] * 0.45);     // Green down
            d[i+2] = Math.round(d[i+2] * 0.70);     // Blue stronger
        }
        ctx.putImageData(imgData, 0, 0);

        // Add subtle golden gradient lighting to windows / central area
        const grad = ctx.createRadialGradient(w / 2, h / 2, 40, w / 2, h / 2, w * 0.85);
        grad.addColorStop(0, 'rgba(255, 220, 140, 0.20)');
        grad.addColorStop(1, 'rgba(0, 5, 20, 0.45)');

        ctx.save();
        ctx.globalCompositeOperation = 'screen';
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);
        ctx.restore();
    };

    // Drag handle for split screen
    const handleSplitDrag = useCallback((clientX) => {
        if (!sliderContainerRef.current) return;
        const rect = sliderContainerRef.current.getBoundingClientRect();
        const posX = clientX - rect.left;
        const pct = Math.max(0, Math.min(100, (posX / rect.width) * 100));
        setSliderPos(pct);
    }, []);

    const handleMouseDown = () => setIsDragging(true);

    useEffect(() => {
        const handleMouseMove = (e) => {
            if (!isDragging) return;
            handleSplitDrag(e.clientX);
        };
        const handleMouseUp = () => setIsDragging(false);

        if (isDragging) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, handleSplitDrag]);

    // Flood Fill click detection
    const handleCanvasClick = (e) => {
        if (!imgElement || !canvasRef.current) return;
        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();

        // Client mouse coords
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;

        // Map to original canvas resolution coordinates
        const x = Math.round((mx / rect.width) * canvas.width);
        const y = Math.round((my / rect.height) * canvas.height);

        // Read original image data
        const origCanvas = document.createElement('canvas');
        origCanvas.width = canvas.width;
        origCanvas.height = canvas.height;
        const oCtx = origCanvas.getContext('2d');
        oCtx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);
        const imgData = oCtx.getImageData(0, 0, canvas.width, canvas.height);

        // Perform flood fill to isolate the paintable region
        const mask = floodFillAlg(imgData, x, y, tolerance);
        if (!mask) return;

        // Update region mask: Merge if existing or replace
        const updatedMasks = { ...masks };
        if (updatedMasks[activeRegion]) {
            // Merge masks to allow multiple walls/regions to paint with one color
            const merged = new Uint8Array(mask.length);
            for (let i = 0; i < mask.length; i++) {
                merged[i] = updatedMasks[activeRegion][i] || mask[i];
            }
            updatedMasks[activeRegion] = merged;
        } else {
            updatedMasks[activeRegion] = mask;
        }

        const updatedColors = {
            ...appliedColors,
            [activeRegion]: selectedColor.hex
        };

        saveHistory(updatedColors, updatedMasks);
        setMasks(updatedMasks);
        setAppliedColors(updatedColors);

        showGlobalToast(`Đã tô màu ${selectedColor.name} (${selectedColor.code}) lên ${REGION_LABELS[activeRegion].name}!`);
    };

    // Flood Fill BFS implementation
    const floodFillAlg = (imageData, startX, startY, tol) => {
        const w = imageData.width;
        const h = imageData.height;
        const d = imageData.data;

        const mask = new Uint8Array(w * h);
        const visited = new Uint8Array(w * h);

        const startIdx = (startY * w + startX) * 4;
        const startR = d[startIdx];
        const startG = d[startIdx + 1];
        const startB = d[startIdx + 2];
        const startA = d[startIdx + 3];

        if (startA < 15) return null; // Avoid transparent pixels

        const queue = [];
        queue.push(startX, startY);
        visited[startY * w + startX] = 1;

        const tolSq = tol * tol;

        let head = 0;
        while (head < queue.length) {
            const cx = queue[head++];
            const cy = queue[head++];

            const idx = cy * w + cx;
            mask[idx] = 255;

            const neighbors = [
                cx - 1, cy,
                cx + 1, cy,
                cx, cy - 1,
                cx, cy + 1
            ];

            for (let i = 0; i < 8; i += 2) {
                const nx = neighbors[i];
                const ny = neighbors[i+1];

                if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
                    const nidx = ny * w + nx;
                    if (!visited[nidx]) {
                        visited[nidx] = 1;
                        const pixelIdx = nidx * 4;
                        const r = d[pixelIdx];
                        const g = d[pixelIdx + 1];
                        const b = d[pixelIdx + 2];
                        const a = d[pixelIdx + 3];

                        if (a >= 15) {
                            const dr = r - startR;
                            const dg = g - startG;
                            const db = b - startB;
                            const distSq = dr*dr + dg*dg + db*db;
                            if (distSq <= tolSq) {
                                queue.push(nx, ny);
                            }
                        }
                    }
                }
            }
        }
        return mask;
    };

    // File upload parsing
    const handleFileUpload = (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                setImageSrc(ev.target.result);
            };
            reader.readAsDataURL(file);
        }
    };

    const triggerFilePicker = () => {
        if (fileInputRef.current) fileInputRef.current.click();
    };

    const handleDragOver = (e) => {
        e.preventDefault();
    };

    const handleDrop = (e) => {
        e.preventDefault();
        const file = e.dataTransfer.files && e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                setImageSrc(ev.target.result);
            };
            reader.readAsDataURL(file);
        }
    };

    // AI Processing Action
    const runAIColorization = async () => {
        if (!imageSrc) return;
        setAnalyzing(true);

        // Retrieve current active sample template seeds if applicable
        const activeSample = SAMPLE_IMAGES.find(s => s.src === imageSrc);

        if (apiKey) {
            // Real Gemini SDK query flow
            try {
                // Extract base64 image data
                const base64Data = imageSrc.split(',')[1];
                const mimeType = imageSrc.split(';')[0].split(':')[1];

                // Dynamically import @google/genai module
                const { GoogleGenAI } = await import('https://esm.sh/@google/genai');
                const ai = new GoogleGenAI({ apiKey });

                const response = await ai.models.generateContent({
                    model: 'gemini-2.5-flash',
                    contents: [
                        { inlineData: { data: base64Data, mimeType: mimeType } },
                        'Perform automatic paint color scheme coordination for this house. Output JSON matching the specified instructions.'
                    ],
                    config: {
                        systemInstruction: SYSTEM_PROMPT,
                        responseMimeType: 'application/json'
                    }
                });

                const parsedReport = JSON.parse(response.text);
                setAiReport(parsedReport);

                // Apply the suggested colors to regions
                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = canvasRef.current.width;
                tempCanvas.height = canvasRef.current.height;
                const tCtx = tempCanvas.getContext('2d');
                tCtx.drawImage(imgElement, 0, 0, tempCanvas.width, tempCanvas.height);
                const imgData = tCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);

                const nextMasks = { ...masks };
                const nextColors = { ...appliedColors };

                // Seed values helper
                const applySeedColors = (seeds, primaryHex, accentHex) => {
                    // Color Walls
                    if (seeds.wall) {
                        seeds.wall.forEach(pt => {
                            const px = Math.round((pt.x / 900) * tempCanvas.width);
                            const py = Math.round((pt.y / 540) * tempCanvas.height);
                            const mask = floodFillAlg(imgData, px, py, 35);
                            if (mask) {
                                if (!nextMasks.wall) nextMasks.wall = mask;
                                else {
                                    const merged = new Uint8Array(mask.length);
                                    for (let i = 0; i < mask.length; i++) merged[i] = nextMasks.wall[i] || mask[i];
                                    nextMasks.wall = merged;
                                }
                            }
                        });
                        nextColors.wall = primaryHex;
                    }

                    // Color Accents / Columns
                    if (seeds.accent) {
                        seeds.accent.forEach(pt => {
                            const px = Math.round((pt.x / 900) * tempCanvas.width);
                            const py = Math.round((pt.y / 540) * tempCanvas.height);
                            const mask = floodFillAlg(imgData, px, py, 35);
                            if (mask) nextMasks.accent = mask;
                        });
                        nextColors.accent = accentHex;
                    }

                    // Color Roof
                    if (seeds.roof) {
                        seeds.roof.forEach(pt => {
                            const px = Math.round((pt.x / 900) * tempCanvas.width);
                            const py = Math.round((pt.y / 540) * tempCanvas.height);
                            const mask = floodFillAlg(imgData, px, py, 35);
                            if (mask) nextMasks.roof = mask;
                        });
                        nextColors.roof = '#4B5563'; // Neutral gray roof fallback
                    }

                    // Color Trims
                    if (seeds.trim) {
                        seeds.trim.forEach(pt => {
                            const px = Math.round((pt.x / 900) * tempCanvas.width);
                            const py = Math.round((pt.y / 540) * tempCanvas.height);
                            const mask = floodFillAlg(imgData, px, py, 35);
                            if (mask) nextMasks.trim = mask;
                        });
                        nextColors.trim = '#FFFFFF';
                    }
                };

                if (activeSample) {
                    applySeedColors(activeSample.seeds, parsedReport.primaryPaint.hex, parsedReport.accentPaint.hex);
                } else {
                    // Guess coordinates for custom uploads (Walls centered, Accent right, Trim bottom)
                    const centerSeeds = {
                        wall: [{ x: Math.round(tempCanvas.width * 0.4), y: Math.round(tempCanvas.height * 0.55) }],
                        accent: [{ x: Math.round(tempCanvas.width * 0.75), y: Math.round(tempCanvas.height * 0.5) }],
                        roof: [{ x: Math.round(tempCanvas.width * 0.5), y: Math.round(tempCanvas.height * 0.25) }],
                        trim: [{ x: Math.round(tempCanvas.width * 0.3), y: Math.round(tempCanvas.height * 0.7) }]
                    };
                    applySeedColors(centerSeeds, parsedReport.primaryPaint.hex, parsedReport.accentPaint.hex);
                }

                saveHistory(nextColors, nextMasks);
                setMasks(nextMasks);
                setAppliedColors(nextColors);
                showGlobalToast('✨ AI đã phối màu kiến trúc thông minh thành công!');

            } catch (err) {
                console.error('Gemini API Error:', err);
                showGlobalToast('❌ Lỗi kết nối API Gemini. Đang chuyển sang Demo Mode.', 'danger');
                runMockAIColorization(activeSample);
            }
        } else {
            // Demo Mode Simulation
            await new Promise(r => setTimeout(r, 2200));
            runMockAIColorization(activeSample);
        }

        setAnalyzing(false);
    };

    const runMockAIColorization = (activeSample) => {
        const nextMasks = { ...masks };
        const nextColors = { ...appliedColors };

        // Determine architectural style & color recommendations based on uploaded image
        const mockStyles = [
            {
                style: 'Hiện đại tối giản (Modern Minimalist)',
                primary: { code: 'GY-502', name: 'Xám ghi hiện đại', hex: '#6E7A8A', brand: 'Jotun' },
                accent: { code: 'OW-101', name: 'Trắng tinh khôi', hex: '#F4F5F6', brand: 'Dulux' },
                reasoning: 'Phong cách hiện đại đề cao sự thanh lịch và tối giản. Sử dụng tông màu xám làm chủ đạo kết hợp viền trắng giúp tôn vinh đường nét hình học vuông vức của biệt thự.'
            },
            {
                style: 'Tân cổ điển sang trọng (Neoclassical Luxury)',
                primary: { code: 'CR-201', name: 'Kem Cát Ấm', hex: '#F2E7D5', brand: 'Dulux' },
                accent: { code: 'GD-802', name: 'Vàng Cổ Điển', hex: '#CBB285', brand: 'Kova' },
                reasoning: 'Sự pha trộn giữa kem cát ấm và chỉ vàng hoàng gia gợi nên không gian sống quý tộc cổ điển. Màu sắc bắt sáng tốt làm nổi bật phào chỉ tinh xảo.'
            }
        ];

        const chosen = mockStyles[activeSample ? (activeSample.id === 'sample-2' ? 1 : 0) : 0];
        setAiReport({
            architecturalStyle: chosen.style,
            primaryPaint: chosen.primary,
            accentPaint: chosen.accent,
            designReasoning: chosen.reasoning
        });

        // Perform image processing on canvas using simulated coordinates
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = canvasRef.current.width;
        tempCanvas.height = canvasRef.current.height;
        const tCtx = tempCanvas.getContext('2d');
        tCtx.drawImage(imgElement, 0, 0, tempCanvas.width, tempCanvas.height);
        const imgData = tCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);

        const applySeeds = (seeds) => {
            if (seeds.wall) {
                seeds.wall.forEach(pt => {
                    const px = Math.round((pt.x / 900) * tempCanvas.width);
                    const py = Math.round((pt.y / 540) * tempCanvas.height);
                    const mask = floodFillAlg(imgData, px, py, 35);
                    if (mask) {
                        if (!nextMasks.wall) nextMasks.wall = mask;
                        else {
                            const merged = new Uint8Array(mask.length);
                            for (let i = 0; i < mask.length; i++) merged[i] = nextMasks.wall[i] || mask[i];
                            nextMasks.wall = merged;
                        }
                    }
                });
                nextColors.wall = chosen.primary.hex;
            }
            if (seeds.accent) {
                seeds.accent.forEach(pt => {
                    const px = Math.round((pt.x / 900) * tempCanvas.width);
                    const py = Math.round((pt.y / 540) * tempCanvas.height);
                    const mask = floodFillAlg(imgData, px, py, 35);
                    if (mask) nextMasks.accent = mask;
                });
                nextColors.accent = chosen.accent.hex;
            }
            if (seeds.roof) {
                seeds.roof.forEach(pt => {
                    const px = Math.round((pt.x / 900) * tempCanvas.width);
                    const py = Math.round((pt.y / 540) * tempCanvas.height);
                    const mask = floodFillAlg(imgData, px, py, 35);
                    if (mask) nextMasks.roof = mask;
                });
                nextColors.roof = '#2D3238'; // Dark charcoal roof
            }
            if (seeds.trim) {
                seeds.trim.forEach(pt => {
                    const px = Math.round((pt.x / 900) * tempCanvas.width);
                    const py = Math.round((pt.y / 540) * tempCanvas.height);
                    const mask = floodFillAlg(imgData, px, py, 35);
                    if (mask) nextMasks.trim = mask;
                });
                nextColors.trim = '#FFFFFF';
            }
        };

        if (activeSample) {
            applySeeds(activeSample.seeds);
        } else {
            // Fallback for custom image uploads
            const centerSeeds = {
                wall: [{ x: Math.round(tempCanvas.width * 0.45), y: Math.round(tempCanvas.height * 0.6) }],
                accent: [{ x: Math.round(tempCanvas.width * 0.75), y: Math.round(tempCanvas.height * 0.5) }],
                roof: [{ x: Math.round(tempCanvas.width * 0.5), y: Math.round(tempCanvas.height * 0.25) }],
                trim: [{ x: Math.round(tempCanvas.width * 0.35), y: Math.round(tempCanvas.height * 0.75) }]
            };
            applySeeds(centerSeeds);
        }

        saveHistory(nextColors, nextMasks);
        setMasks(nextMasks);
        setAppliedColors(nextColors);
        showGlobalToast('✨ AI đã phối màu kiến trúc thông minh thành công (Demo Mode)!');
    };

    // Export PDF Blueprint Report
    const handleExportPDF = () => {
        if (!canvasRef.current) return;
        showGlobalToast('🖨 Đang chuẩn bị bản in thiết kế kiến trúc...');

        // Open print window containing report details
        const printWindow = window.open('', '_blank');
        const dataUrl = canvasRef.current.toDataURL('image/png');
        
        const originalDataUrl = imgElement.src;

        printWindow.document.write(`
            <html>
            <head>
                <title>Bản vẽ thiết kế phối màu sơn AI - AICOLOR PRO</title>
                <style>
                    body { font-family: 'Plus Jakarta Sans', sans-serif; color: #1e293b; padding: 40px; background-color: #ffffff; }
                    .header { display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; margin-bottom: 30px; }
                    .header h1 { font-size: 24px; color: #4f46e5; margin: 0; }
                    .header p { margin: 5px 0 0 0; color: #64748b; font-size: 13px; }
                    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
                    .card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; text-align: center; }
                    .card h3 { margin-top: 0; font-size: 14px; color: #64748b; text-transform: uppercase; }
                    .card img { width: 100%; height: 220px; object-fit: cover; border-radius: 6px; }
                    .report-section { background-color: #f8fafc; border-radius: 8px; padding: 20px; margin-bottom: 30px; border-left: 4px solid #4f46e5; }
                    .report-section h2 { margin-top: 0; font-size: 16px; color: #1e293b; }
                    .color-badges { display: flex; gap: 15px; margin-top: 15px; }
                    .badge { display: flex; align-items: center; gap: 10px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 12px; font-size: 12px; }
                    .color-box { width: 24px; height: 24px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.1); }
                    .footer { font-size: 11px; text-align: center; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 15px; margin-top: 50px; }
                    @media print {
                        body { padding: 0; }
                        button { display: none; }
                    }
                </style>
            </head>
            <body>
                <div class="header">
                    <div>
                        <h1>AICOLOR PRO - BẢN THIẾT KẾ PHỐI MÀU KIẾN TRÚC</h1>
                        <p>Hệ thống phân tách và tự động phối màu sơn 3D bằng công nghệ AI</p>
                    </div>
                    <div style="text-align: right;">
                        <button onclick="window.print()" style="background-color: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer;">In bản vẽ / Lưu PDF</button>
                    </div>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h3>Bản vẽ gốc (Before)</h3>
                        <img src="${originalDataUrl}" />
                    </div>
                    <div class="card">
                        <h3>Bản phối màu hoàn thiện (After)</h3>
                        <img src="${dataUrl}" />
                    </div>
                </div>

                <div class="report-section">
                    <h2>Thông tin phân tích & đề xuất từ kiến trúc sư AI</h2>
                    <p><strong>Phong cách kiến trúc:</strong> ${aiReport ? aiReport.architecturalStyle : 'Nhận diện tự động'}</p>
                    <p><strong>Lý do thiết kế:</strong> ${aiReport ? aiReport.designReasoning : 'Phối màu theo sở thích cá nhân người dùng.'}</p>
                    
                    <div style="margin-top: 20px;">
                        <strong>Danh sách mã màu sơn áp dụng:</strong>
                        <div class="color-badges">
                            ${Object.keys(appliedColors).map(key => {
                                if (!appliedColors[key]) return '';
                                return `
                                    <div class="badge">
                                        <div class="color-box" style="background-color: ${appliedColors[key]}"></div>
                                        <div>
                                            <strong>${REGION_LABELS[key].name}</strong><br/>
                                            <span style="color: #64748b;">Mã Hex: ${appliedColors[key]}</span>
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                </div>

                <div class="footer">
                    Bản thiết kế được xuất bởi hệ thống AI Phối Màu ArchiColor Pro v2.4.0 · Bản quyền thuộc về ArchiColor Pro © 2026.
                </div>
            </body>
            </html>
        `);
        printWindow.document.close();
    };

    return (
        <div className="flex flex-col lg:flex-row w-full h-full bg-surface text-on-surface font-sans overflow-hidden">
            {/* ════ LEFT PANEL: PaintAI 3-Step Wizard ════ */}
            <aside className="w-full lg:w-[420px] shrink-0 overflow-y-auto p-6 lg:p-8">
                
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-outline-variant flex flex-col gap-6 sticky top-0">
                    
                    {/* STEP 1: Choose Interior / Exterior */}
                    {step === 1 && (
                        <div className="space-y-6">
                            <div className="text-center mb-8">
                                <h3 className="text-xl font-bold mb-2 text-on-surface">Đây là công trình nội thất hay ngoại thất?</h3>
                                <p className="text-on-surface-variant text-sm">Chọn đúng loại sẽ giúp AI xác định các chi tiết kiến trúc chính xác hơn.</p>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <button 
                                    onClick={() => { setBuildingType('interior'); setStep(2); }}
                                    className="group flex flex-col items-center text-center p-6 border-2 border-outline-variant rounded-2xl hover:border-primary hover:bg-primary/5 transition-all text-on-surface"
                                >
                                    <div className="w-16 h-16 rounded-2xl bg-surface-container flex items-center justify-center mb-4 group-hover:bg-primary/10 transition-colors">
                                        <i className="fa-solid fa-couch text-2xl text-on-surface-variant group-hover:text-primary"></i>
                                    </div>
                                    <h4 className="font-bold text-base mb-2">Nội thất</h4>
                                    <p className="text-[10px] text-on-surface-variant">Phòng khách, phòng ngủ, bếp...</p>
                                </button>
                                <button 
                                    onClick={() => { setBuildingType('exterior'); setStep(2); }}
                                    className="group flex flex-col items-center text-center p-6 border-2 border-outline-variant rounded-2xl hover:border-primary hover:bg-primary/5 transition-all text-on-surface"
                                >
                                    <div className="w-16 h-16 rounded-2xl bg-surface-container flex items-center justify-center mb-4 group-hover:bg-primary/10 transition-colors">
                                        <i className="fa-solid fa-house text-2xl text-on-surface-variant group-hover:text-primary"></i>
                                    </div>
                                    <h4 className="font-bold text-base mb-2">Ngoại thất</h4>
                                    <p className="text-[10px] text-on-surface-variant">Mặt tiền, sân vườn, hàng rào...</p>
                                </button>
                            </div>
                        </div>
                    )}

                    {/* STEP 2: Upload Image */}
                    {step === 2 && (
                        <div className="space-y-6">
                            <div 
                                onDragOver={handleDragOver}
                                onDrop={handleDrop}
                                onClick={triggerFilePicker}
                                className="border-2 border-dashed border-outline-variant rounded-xl p-10 flex flex-col items-center justify-center group hover:border-primary hover:bg-primary/5 cursor-pointer transition-all"
                            >
                                <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept="image/*" className="hidden" />
                                <div className="w-12 h-12 bg-surface-container rounded-full flex items-center justify-center mb-4 group-hover:bg-primary/10 transition-colors">
                                    <i className="fa-solid fa-cloud-arrow-up text-lg text-on-surface-variant group-hover:text-primary"></i>
                                </div>
                                <p className="font-semibold text-on-surface mb-1 text-center">Nhấn để tải lên <span className="text-on-surface-variant font-normal text-sm">hoặc kéo và thả</span></p>
                                <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider">PNG, JPG, hoặc WEBP (tối đa 10MB)</p>
                            </div>
                            <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl space-y-3">
                                <div className="flex items-center gap-2">
                                    <i className="fa-solid fa-lightbulb text-amber-600"></i>
                                    <span className="font-bold text-sm text-amber-700">Mẹo để có kết quả tốt nhất:</span>
                                </div>
                                <ul className="space-y-2 text-xs text-amber-800 font-medium">
                                    <li className="flex gap-2"><div className="w-1 h-1 rounded-full bg-amber-500 mt-1.5 shrink-0"></div>Sử dụng ảnh rõ nét, độ phân giải cao.</li>
                                    <li className="flex gap-2"><div className="w-1 h-1 rounded-full bg-amber-500 mt-1.5 shrink-0"></div>Đảm bảo không gian có ánh sáng tốt và đều.</li>
                                </ul>
                            </div>
                            <div>
                                <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-2.5">Hoặc chọn ảnh mẫu:</span>
                                <div className="grid grid-cols-2 gap-2">
                                    {SAMPLE_IMAGES.map(sample => (
                                        <button key={sample.id} onClick={() => setImageSrc(sample.src)}
                                            className="p-1.5 border border-outline-variant hover:border-primary bg-white rounded-lg overflow-hidden text-left hover:scale-[1.02] transition duration-200">
                                            <img src={sample.src} className="w-full h-16 object-cover rounded-md mb-1.5" />
                                            <span className="text-[10px] font-bold text-on-surface block truncate px-1">{sample.name}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <button onClick={() => setStep(1)} className="w-full py-2 text-on-surface-variant font-bold text-xs uppercase tracking-widest hover:text-primary transition-colors">Quay lại</button>
                        </div>
                    )}
                ) : (
                    <div className="flex flex-col gap-4">
                        
                        {/* Toggle view buttons */}
                        <button 
                            onClick={() => setView('upload')}
                            className="w-full py-1.5 px-3 bg-slate-800/80 hover:bg-slate-800 text-xs font-semibold rounded-lg border border-slate-700 flex items-center justify-center gap-1.5 transition text-slate-300"
                        >
                            ← Chọn bức ảnh khác
                        </button>

                        {/* AI Mode Toggle with slide animation */}
                        <div className="bg-slate-900/60 p-1.5 rounded-xl border border-slate-800 flex items-center relative overflow-hidden">
                            <button 
                                onClick={() => setAiMode('auto')}
                                className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all relative z-10 ${aiMode === 'auto' ? 'text-white' : 'text-slate-400'}`}
                            >
                                ✨ AI Tự Động
                            </button>
                            <button 
                                onClick={() => setAiMode('manual')}
                                className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all relative z-10 ${aiMode === 'manual' ? 'text-white' : 'text-slate-400'}`}
                            >
                                🎨 Tự Chọn Thủ Công
                            </button>
                            <div 
                                className="absolute top-1.5 bottom-1.5 bg-indigo-600 rounded-lg transition-all duration-300"
                                style={{
                                    width: 'calc(50% - 6px)',
                                    left: aiMode === 'auto' ? '6px' : 'calc(50% - 0px)'
                                }}
                            />
                        </div>

                        {/* AI Mode Specific control blocks */}
                        {aiMode === 'auto' ? (
                            <div className="bg-indigo-950/20 border border-indigo-500/20 p-3.5 rounded-xl flex flex-col gap-3">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-xs">🤖</span>
                                        <h4 className="text-xs font-extrabold text-indigo-300 uppercase tracking-wider">Trí tuệ nhân tạo AI</h4>
                                    </div>
                                    <button 
                                        onClick={() => setShowApiKeyModal(true)}
                                        className="text-[9px] text-indigo-400 hover:text-indigo-300 underline font-semibold"
                                    >
                                        {apiKey ? 'Thay khóa API' : 'Cấu hình API Key'}
                                    </button>
                                </div>
                                <p className="text-[10px] text-slate-300 leading-normal">
                                    AI sẽ tự phân tích kết cấu và phối các tông màu sơn ngoại thất phù hợp nhất với bản vẽ.
                                </p>
                                <button 
                                    onClick={runAIColorization}
                                    disabled={analyzing}
                                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/40 text-xs font-bold rounded-lg text-white shadow-lg shadow-indigo-600/20 hover:shadow-indigo-500/40 active:scale-98 transition flex items-center justify-center gap-2"
                                >
                                    {analyzing ? (
                                        <>
                                            <i className="fa-solid fa-spinner fa-spin"></i>
                                            <span>Đang xử lý phối màu...</span>
                                        </>
                                    ) : (
                                        <>
                                            <i className="fa-solid fa-bolt-lightning"></i>
                                            <span>Xử Lý Phối Màu AI</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        ) : (
                            <div className="flex flex-col gap-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                    Chọn phân vùng muốn sơn:
                                </label>
                                <div className="grid grid-cols-2 gap-1.5">
                                    {Object.keys(REGION_LABELS).map(key => {
                                        const isActive = activeRegion === key;
                                        const applied = appliedColors[key];
                                        return (
                                            <button 
                                                key={key}
                                                onClick={() => setActiveRegion(key)}
                                                className={`p-2 border rounded-lg flex items-center justify-between text-left transition duration-200 ${isActive ? 'border-indigo-500 bg-indigo-500/5 shadow-sm' : 'border-slate-800 bg-slate-900/30'}`}
                                            >
                                                <span className="text-[10px] font-bold text-slate-200">
                                                    {REGION_LABELS[key].icon} {REGION_LABELS[key].name}
                                                </span>
                                                <div 
                                                    className="w-3.5 h-3.5 rounded-full border border-slate-700 shadow-inner shrink-0 ml-1.5"
                                                    style={{ backgroundColor: applied || '#FFFFFF' }}
                                                />
                                            </button>
                                        );
                                    })}
                                </div>

                                {/* Magic wand tolerance slider */}
                                <div className="mt-2 p-2.5 bg-slate-900/30 border border-slate-850 rounded-xl">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-[9px] font-bold text-slate-400 uppercase">Độ nhạy đũa phép (Wand):</span>
                                        <span className="text-[10px] font-mono text-indigo-400 font-bold">{tolerance} px</span>
                                    </div>
                                    <input 
                                        type="range" 
                                        min="5" 
                                        max="70" 
                                        value={tolerance}
                                        onChange={(e) => setTolerance(parseInt(e.target.value))}
                                        className="w-full accent-indigo-500 h-1 bg-slate-800 rounded-lg cursor-pointer"
                                    />
                                </div>
                            </div>
                        )}

                        {/* Color Palette Matrix */}
                        <div className="flex flex-col gap-2">
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center justify-between">
                                <span>Ma Trận Bảng Màu:</span>
                                <span className="text-[9px] text-indigo-400 font-bold bg-indigo-500/10 px-1.5 py-0.5 rounded uppercase">Màu thực tế</span>
                            </label>

                            {/* Tabs for themes */}
                            <div className="grid grid-cols-4 gap-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800">
                                {Object.keys(PALETTE_GROUPS).map(key => (
                                    <button
                                        key={key}
                                        onClick={() => setSelectedTheme(key)}
                                        className={`py-1 rounded text-[9px] font-bold transition-all ${selectedTheme === key ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
                                    >
                                        {PALETTE_GROUPS[key].name}
                                    </button>
                                ))}
                            </div>

                            {/* Colors Grid */}
                            <div className="grid grid-cols-3 gap-1.5 max-h-40 overflow-y-auto pr-1">
                                {PALETTE_GROUPS[selectedTheme].colors.map(color => {
                                    const isApplied = aiMode === 'manual' 
                                        ? appliedColors[activeRegion] === color.hex
                                        : Object.values(appliedColors).includes(color.hex);
                                    const isSelected = selectedColor.code === color.code;

                                    return (
                                        <button 
                                            key={color.code}
                                            onClick={() => {
                                                setSelectedColor(color);
                                                if (aiMode === 'manual') {
                                                    const updatedColors = { ...appliedColors, [activeRegion]: color.hex };
                                                    saveHistory(updatedColors, masks);
                                                    setAppliedColors(updatedColors);
                                                    showGlobalToast(`Đã sơn màu ${color.name} (${color.code}) cho ${REGION_LABELS[activeRegion].name}`);
                                                }
                                            }}
                                            className={`p-1.5 border rounded-lg bg-slate-900/40 hover:bg-slate-900 hover:border-slate-700 transition flex flex-col items-center justify-center relative select-none ${isSelected ? 'border-indigo-500 bg-indigo-500/5' : 'border-slate-800'}`}
                                            title={`${color.code} - ${color.name}`}
                                        >
                                            <div 
                                                className="w-7 h-7 rounded-full border border-slate-700 shadow-inner mb-1 active:scale-110 transition"
                                                style={{ backgroundColor: color.hex }}
                                            />
                                            <span className="text-[8px] font-bold text-slate-200 truncate w-full text-center">{color.code}</span>
                                            <span className="text-[7px] text-slate-500 truncate w-full text-center">{color.name}</span>
                                            
                                            {isApplied && (
                                                <div className="absolute top-0.5 right-0.5 w-2 h-2 bg-indigo-500 rounded-full flex items-center justify-center shadow">
                                                    <i className="fa-solid fa-check text-[5px] text-white"></i>
                                                </div>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Interactive Sliders */}
                        <div className="flex flex-col gap-2.5 p-3 bg-slate-900/30 border border-slate-850 rounded-xl">
                            <div>
                                <div className="flex justify-between items-center mb-1">
                                    <span className="text-[9px] font-bold text-slate-400 uppercase">Độ mờ màu Trước/Sau:</span>
                                    <span className="text-[10px] font-mono text-indigo-400 font-bold">{opacitySlider}%</span>
                                </div>
                                <input 
                                    type="range" 
                                    min="10" 
                                    max="100" 
                                    value={opacitySlider}
                                    onChange={(e) => setOpacitySlider(parseInt(e.target.value))}
                                    className="w-full accent-indigo-500 h-1 bg-slate-800 rounded-lg cursor-pointer"
                                />
                            </div>

                            <div className="flex items-center justify-between border-t border-slate-800/80 pt-2.5 mt-0.5">
                                <span className="text-[9px] font-bold text-slate-400 uppercase">Chế độ xem Ngày / Đêm:</span>
                                <div className="flex items-center gap-1.5">
                                    <button 
                                        onClick={() => setDayNight('day')}
                                        className={`p-1 text-xs rounded-md transition ${dayNight === 'day' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}`}
                                        title="Ảnh ban ngày"
                                    >
                                        ☀️
                                    </button>
                                    <button 
                                        onClick={() => setDayNight('night')}
                                        className={`p-1 text-xs rounded-md transition ${dayNight === 'night' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'}`}
                                        title="Phối cảnh ban đêm"
                                    >
                                        🌙
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Undo / Redo & Action buttons */}
                        <div className="flex gap-2">
                            <button 
                                onClick={handleUndo}
                                disabled={historyIndex < 0}
                                className="flex-1 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:pointer-events-none transition rounded-lg text-[10px] font-bold flex items-center justify-center gap-1 border border-slate-700"
                            >
                                ↩ Hoàn tác
                            </button>
                            <button 
                                onClick={handleRedo}
                                disabled={historyIndex >= history.length - 1}
                                className="flex-1 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:pointer-events-none transition rounded-lg text-[10px] font-bold flex items-center justify-center gap-1 border border-slate-700"
                            >
                                ↪ Làm lại
                            </button>
                            <button 
                                onClick={handleReset}
                                className="px-2 py-1.5 bg-slate-800 hover:bg-slate-700 transition rounded-lg text-[10px] font-bold flex items-center justify-center border border-slate-700 text-red-400"
                                title="Xóa hết"
                            >
                                🗑️
                            </button>
                        </div>

                        <button 
                            onClick={handleExportPDF}
                            className="w-full py-2 border border-indigo-500/20 bg-indigo-600/10 hover:bg-indigo-600 text-indigo-400 hover:text-white text-xs font-bold rounded-lg transition duration-200 flex items-center justify-center gap-1.5"
                        >
                            📄 Xuất Bản Vẽ PDF
                        </button>

                    </div>
                )}
            </aside>

            {/* ════ KHÔNG GIAN TRỰC QUAN BÊN PHẢI (2/3 Width) ════ */}
            <main className="flex-1 bg-[#050811] flex flex-col items-center justify-center relative p-4 md:p-6 overflow-hidden">
                
                {/* Pre-loading and analyzing screen overlay */}
                {analyzing && (
                    <div className="absolute inset-0 bg-[#050811]/95 z-40 flex flex-col items-center justify-center gap-4 animate-fade-in">
                        <div className="flex gap-2">
                            <span className="w-3.5 h-3.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '-0.3s' }}></span>
                            <span className="w-3.5 h-3.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '-0.15s' }}></span>
                            <span className="w-3.5 h-3.5 bg-indigo-500 rounded-full animate-bounce"></span>
                        </div>
                        <div className="text-center animate-slide-in-up">
                            <h3 className="text-sm font-extrabold text-indigo-300 uppercase tracking-widest">Hệ thống đang tiền xử lý công trình</h3>
                            <p className="text-xs text-slate-400 mt-1.5">Trích xuất cấu trúc hình khối & phối sơn 3D nâng cao...</p>
                        </div>
                    </div>
                )}

                {view === 'upload' ? (
                    <div className="flex flex-col items-center justify-center text-center max-w-md p-6">
                        <div className="text-5xl mb-4 animate-pulse">✨</div>
                        <h2 className="text-xl font-black text-slate-200">Trợ Lý Phối Màu Kiến Trúc AI</h2>
                        <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                            Upload bản thiết kế hoặc hình chụp thực tế của ngôi nhà. AI sẽ phân tách các lớp kiến trúc và tự động hòa trộn các dải màu sơn chân thực nhất.
                        </p>
                        <button 
                            onClick={triggerFilePicker}
                            className="mt-5 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-bold rounded-xl text-white shadow-lg shadow-indigo-600/25 active:scale-98 transition flex items-center gap-2"
                        >
                            📤 Chọn Ảnh Công Trình
                        </button>
                    </div>
                ) : (
                    <div className="w-full h-full flex flex-col relative">
                        {/* Toolbar details */}
                        <div className="flex items-center justify-between pb-3 border-b border-slate-900 mb-3 shrink-0">
                            <div>
                                <h3 className="text-xs font-bold text-slate-200">Trình trực quan phối cảnh AI</h3>
                                <p className="text-[10px] text-slate-400 mt-0.5">
                                    {aiMode === 'auto' 
                                        ? 'Chế độ AI tự động: bấm "Xử Lý Phối Màu AI" để áp dụng.' 
                                        : `Chế độ thủ công: Chọn vùng và click trực tiếp lên ảnh để tô màu. Đang tô: ${REGION_LABELS[activeRegion].name}`}
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                {aiReport && (
                                    <div className="text-right">
                                        <span className="text-[9px] font-bold text-indigo-400 block">{aiReport.architecturalStyle}</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Canvas Split view container */}
                        <div 
                            ref={sliderContainerRef}
                            className="flex-1 relative w-full h-full flex items-center justify-center overflow-hidden rounded-xl border border-slate-900 bg-slate-950/20"
                        >
                            <canvas 
                                ref={canvasRef}
                                onClick={aiMode === 'manual' ? handleCanvasClick : undefined}
                                className={`max-w-full max-h-full object-contain shadow-2xl ${aiMode === 'manual' ? 'cursor-crosshair hover:shadow-indigo-500/5' : 'cursor-default'}`}
                            />
                            
                            {/* Invisible absolute overlay covering the canvas area for drag capturing */}
                            <div 
                                onMouseDown={handleMouseDown}
                                className="absolute inset-0 cursor-ew-resize pointer-events-none"
                            />

                            {/* Floating tooltip for manual mode */}
                            {aiMode === 'manual' && (
                                <div className="absolute top-3 left-3 bg-slate-900/90 backdrop-blur border border-slate-800 px-3 py-1.5 rounded-lg pointer-events-none shadow flex items-center gap-2">
                                    <span className="animate-pulse w-1.5 h-1.5 rounded-full bg-indigo-500" />
                                    <span className="text-[9px] font-medium text-slate-300">Click chuột lên tường trên hình để tô màu</span>
                                </div>
                            )}
                        </div>

                        {/* AI suggestions details section */}
                        {aiReport && (
                            <div className="mt-3.5 bg-indigo-950/15 border border-indigo-900/20 p-3 rounded-lg shrink-0 animate-slide-in-up">
                                <h4 className="text-[10px] font-bold uppercase text-indigo-300 tracking-wider mb-1 flex items-center gap-1.5">
                                    🎨 Nhận định phối màu của AI
                                </h4>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
                                    <div>
                                        <span className="text-[9px] text-slate-500 block">Phong cách</span>
                                        <span className="text-xs font-extrabold text-slate-200 block mt-0.5">{aiReport.architecturalStyle}</span>
                                    </div>
                                    <div>
                                        <span className="text-[9px] text-slate-500 block">Gợi ý màu sơn</span>
                                        <div className="flex gap-2 mt-0.5">
                                            <div className="flex items-center gap-1 text-[10px] font-bold text-slate-300">
                                                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: aiReport.primaryPaint.hex }} />
                                                <span>Chính: {aiReport.primaryPaint.paintCode || aiReport.primaryPaint.name}</span>
                                            </div>
                                            <div className="flex items-center gap-1 text-[10px] font-bold text-slate-300">
                                                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: aiReport.accentPaint.hex }} />
                                                <span>Nhấn: {aiReport.accentPaint.paintCode || aiReport.accentPaint.name}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="md:col-span-1">
                                        <span className="text-[9px] text-slate-500 block">Phân tích chuyên sâu</span>
                                        <p className="text-[10px] text-slate-400 mt-0.5 leading-relaxed">{aiReport.designReasoning}</p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </main>

            {/* ════ FLOATING API KEY CONFIG DIALOG ════ */}
            {showApiKeyModal && (
                <div className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4 backdrop-blur-sm">
                    <div className="bg-[#0f1422] border border-slate-800 p-5 rounded-2xl max-w-sm w-full shadow-2xl animate-scale-in">
                        <h3 className="text-xs font-bold uppercase text-indigo-300 tracking-wider mb-2">Cấu hình API Key Gemini</h3>
                        <p className="text-[10px] text-slate-400 leading-normal mb-4">
                            Để sử dụng trí tuệ nhân tạo AI thực tế xử lý phối màu thông minh, vui lòng nhập khóa API Gemini của bạn. Khóa này chỉ được lưu trữ cục bộ trên trình duyệt của bạn.
                        </p>
                        <input 
                            type="password" 
                            placeholder="Nhập khóa API Gemini của bạn..." 
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-850 px-3 py-2 text-xs text-white rounded-lg focus:border-indigo-500 outline-none placeholder:text-slate-600 mb-4"
                        />
                        <div className="flex gap-2 justify-end">
                            <button 
                                onClick={() => setShowApiKeyModal(false)}
                                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-[10px] font-bold rounded-lg text-slate-300"
                            >
                                Đóng
                            </button>
                            <button 
                                onClick={() => {
                                    setShowApiKeyModal(false);
                                    showGlobalToast('🔑 Đã lưu khóa API thành công!');
                                }}
                                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-[10px] font-bold rounded-lg text-white"
                            >
                                Lưu Khóa
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// Global toast trigger utility
function showGlobalToast(msg, type = 'success') {
    const toast = document.getElementById('toast-notification');
    const text = document.getElementById('toast-message');
    if (!toast || !text) return;
    text.textContent = msg;
    toast.className = 'toast show';
    if (type === 'danger') {
        toast.style.borderColor = 'rgba(239, 68, 68, 0.4)';
    } else {
        toast.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    }
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// Mount to index.html container on script loading
const container = document.getElementById('react-ai-editor-root');
if (container) {
    const root = ReactDOM.createRoot(container);
    root.render(<App />);
}
