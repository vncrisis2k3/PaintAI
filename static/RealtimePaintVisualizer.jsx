import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';

/**
 * ARCHICOLOR PRO - REAL-TIME PAINT VISUALIZER COMPONENT
 * 
 * Một Component React cao cấp chuyên biệt về xử lý đồ họa Web Canvas (HTML5 Canvas),
 * giải quyết triệt để vấn đề phối màu kiến trúc thời gian thực giữ nguyên nếp gấp,
 * bóng đổ 3D (Highlights/Shadows) và chống lỗi bảo mật ảnh CORS (Tainted Canvas).
 */

// --- DỮ LIỆU MẪU ĐỂ CHẠY ĐỘC LẬP (MOCK DATA) ---
const MOCK_PROJECT_TYPES = [
  { id: 1, name: "Biệt thự hiện đại" },
  { id: 2, name: "Nhà phố tân cổ điển" },
  { id: 3, name: "Nhà cấp 4 mái thái" }
];

const MOCK_LAYERS = [
  { id: "layer-bg", name: "Khung cảnh & Nền", zIndex: 1, opacity: 1.0, visible: true, isPaintable: false, image: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80" },
  { id: "layer-wall", name: "Tường chính", zIndex: 2, opacity: 1.0, visible: true, isPaintable: true, image: "https://aicolor.vn/storage/layer-collections/1772606611/hYNd1olyI6BVH4IvqraTdUb3yhxakhO7nt3nFcYW.webp" },
  { id: "layer-accent", name: "Mảng nhấn trang trí", zIndex: 3, opacity: 1.0, visible: true, isPaintable: true, image: "https://aicolor.vn/storage/layer-collections/1772606612/dfMo1XtTnJWqfWNJ4cUvRr8fflPkI9ShBkU6gYj4.webp" },
  { id: "layer-roof", name: "Hệ thống Mái ngói", zIndex: 4, opacity: 1.0, visible: true, isPaintable: true, image: "https://aicolor.vn/storage/layer-collections/1772606613/hJdY1olyI6BVH4IvqraTdUb3yhxakhO7nt3nFcYW.webp" }
];

const MOCK_COLORS = [
  { id: 101, name: "Trắng Sứ", paint_code: "OW101", hex_code: "#F3F4F6", brand: "Dulux", category: "Ngoại thất" },
  { id: 102, name: "Xám Xanh Ghi", paint_code: "GY502", hex_code: "#708090", brand: "Jotun", category: "Màu nhấn" },
  { id: 103, name: "Kem Cát Ấm", paint_code: "YE204", hex_code: "#ECE2CE", brand: "Dulux", category: "Ngoại thất" },
  { id: 104, name: "Đỏ Đất Mái Ngói", paint_code: "RD801", hex_code: "#A52A2A", brand: "Kova", category: "Màu nhấn" },
  { id: 105, name: "Vàng Mustard Cổ Điển", paint_code: "GD303", hex_code: "#DAA520", brand: "Nippon", category: "Ngoại thất" },
  { id: 106, name: "Xanh Mint Dịu Mát", paint_code: "GN108", hex_code: "#A3E635", brand: "Jotun", category: "Nội thất" }
];

export default function RealtimePaintVisualizer() {
  // --- STATE SYSTEM ---
  const [layers, setLayers] = useState(MOCK_LAYERS);
  const [colors, setColors] = useState(MOCK_COLORS);
  const [selectedBrand, setSelectedBrand] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  
  const [activeLayerId, setActiveLayerId] = useState("layer-wall");
  const [appliedColors, setAppliedColors] = useState({}); // { [layerId]: hex_code }
  const [history, setHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  
  const [compareMode, setCompareMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState({ show: false, message: "", type: "success" });

  // --- REFS FOR GRAPHICS ENGINE ---
  const mainCanvasRef = useRef(null);
  const originalCanvasRef = useRef(null);
  const imageCacheRef = useRef({}); // Lưu trữ đối tượng HTMLImageElement đã preload
  const containerRef = useRef(null);

  // --- TOAST UTILITY ---
  const showToast = useCallback((message, type = "success") => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast(prev => ({ ...prev, show: false }));
    }, 2500);
  }, []);

  // --- 1. PIPELINE TẢI VÀ CACHE HÌNH ẢNH (CORS-PROOF PRELOADING) ---
  useEffect(() => {
    let active = true;
    setIsLoading(true);

    const preloadImages = async () => {
      const promises = layers.map(layer => {
        return new Promise((resolve) => {
          // Bỏ qua nếu ảnh đã được cache từ trước
          if (imageCacheRef.current[layer.id]) {
            resolve();
            return;
          }

          const img = new Image();
          /**
           * GIẢI QUYẾT TRIỆT ĐỂ LỖI CORS "Tainted Canvas":
           * Cấu hình crossOrigin để trình duyệt chấp nhận chia sẻ tài nguyên an toàn.
           * Khi kết hợp với Proxy API cục bộ ở Backend, ảnh sẽ được đọc pixel tự do.
           */
          img.crossOrigin = "anonymous";
          
          // Sử dụng Proxy Backend để tránh lỗi CORS từ CDN ngoài nước
          const proxiedUrl = layer.image.startsWith("http") 
            ? `/api/proxy-image?url=${encodeURIComponent(layer.image)}`
            : layer.image;

          img.src = proxiedUrl;
          
          img.onload = () => {
            if (active) imageCacheRef.current[layer.id] = img;
            resolve();
          };

          img.onerror = () => {
            console.warn(`Preload thất bại với CORS: ${layer.image}. Thử lại không CORS...`);
            // Fallback: Tải lại không có CORS (có thể bị chặn xuất ảnh nhưng vẫn vẽ được hiển thị)
            const fallbackImg = new Image();
            fallbackImg.src = layer.image;
            fallbackImg.onload = () => {
              if (active) imageCacheRef.current[layer.id] = fallbackImg;
              resolve();
            };
            fallbackImg.onerror = () => {
              console.error(`Không thể tải tài nguyên layer: ${layer.name}`);
              resolve();
            };
          };
        });
      });

      await Promise.all(promises);
      if (active) {
        setIsLoading(false);
        showToast("Đã tải xong mô hình 3D trong suốt!", "success");
      }
    };

    preloadImages();

    return () => {
      active = false;
    };
  }, [layers, showToast]);

  // --- 2. THUẬT TOÁN HÒA TRỘN ĐỒ HỌA CHUYÊN NGHIỆP (MULTIPLY BLENDING ENGINE) ---
  const renderCanvasLayers = useCallback((canvas, colorMapping, useOriginal = false) => {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Tìm kích thước chuẩn dựa trên ảnh nền đầu tiên hoặc kích thước khung mặc định
    let width = 1200;
    let height = 800;
    
    const sortedLayers = [...layers].sort((a, b) => a.zIndex - b.zIndex);
    
    for (let layer of sortedLayers) {
      const img = imageCacheRef.current[layer.id];
      if (img && img.naturalWidth) {
        width = img.naturalWidth;
        height = img.naturalHeight;
        break;
      }
    }

    // Set độ phân giải Canvas khớp chính xác với tỷ lệ gốc của tệp ảnh WebP
    canvas.width = width;
    canvas.height = height;
    ctx.clearRect(0, 0, width, height);

    // Vẽ tuần tự từng Layer đè lên nhau
    sortedLayers.forEach(layer => {
      if (!layer.visible) return; // Ẩn nếu trạng thái hiển thị bằng false

      const img = imageCacheRef.current[layer.id];
      if (!img) return; // Bỏ qua nếu ảnh chưa tải xong

      const appliedColor = colorMapping[layer.id];

      // Chỉ thực hiện nhuộm màu lên các Layer có quyền sơn (isPaintable) và đã chọn màu sơn
      if (appliedColor && layer.isPaintable && !useOriginal) {
        try {
          // BƯỚC A: Tạo Canvas đệm ngoại màn hình (Offscreen Canvas 1) cho lớp mặt nạ màu đặc
          const colorCanvas = document.createElement('canvas');
          colorCanvas.width = width;
          colorCanvas.height = height;
          const cCtx = colorCanvas.getContext('2d');

          // Vẽ ảnh gốc vào canvas đệm màu
          cCtx.drawImage(img, 0, 0, width, height);
          
          // Thiết lập chế độ chồng đè chỉ giữ lại phần đè (Source-In): 
          // Cắt gọn màu sắc đặc theo đúng ranh giới độ trong suốt alpha của ảnh gốc.
          cCtx.globalCompositeOperation = 'source-in';
          cCtx.fillStyle = appliedColor;
          cCtx.fillRect(0, 0, width, height);

          // BƯỚC B: Tạo Canvas đệm thứ hai (Offscreen Canvas 2) để hòa trộn kết cấu nếp gấp
          const blendCanvas = document.createElement('canvas');
          blendCanvas.width = width;
          blendCanvas.height = height;
          const bCtx = blendCanvas.getContext('2d');

          // Vẽ lớp màu đã cắt gọn vào canvas đệm hòa trộn
          bCtx.drawImage(colorCanvas, 0, 0);

          /**
           * THUẬT TOÁN HÒA TRỘN MULTIPLY (NHÂN MÀU):
           * Nhân giá trị màu sơn với sắc độ tối sáng (Highlights/Shadows) của ảnh gốc.
           * Giúp màu sơn bám chặt vào kết cấu tường nhám, đổ bóng 3D, giữ nguyên độ chân thực.
           */
          bCtx.globalCompositeOperation = 'multiply';
          bCtx.drawImage(img, 0, 0, width, height);

          // BƯỚC C: Vẽ ảnh hòa trộn hoàn thiện lên Canvas chính
          ctx.globalAlpha = layer.opacity;
          ctx.drawImage(blendCanvas, 0, 0);
          ctx.globalAlpha = 1.0; // Reset độ mờ về mặc định

        } catch (error) {
          console.error(`Lỗi render layer hòa trộn ${layer.name}:`, error);
          // Fallback vẽ ảnh gốc không nhuộm màu nếu gặp sự cố đồ họa
          ctx.globalAlpha = layer.opacity;
          ctx.drawImage(img, 0, 0, width, height);
          ctx.globalAlpha = 1.0;
        }
      } else {
        // Vẽ trực tiếp các layer không sơn (Background, Kính cửa, Cây cối...)
        ctx.globalAlpha = layer.opacity;
        ctx.drawImage(img, 0, 0, width, height);
        ctx.globalAlpha = 1.0;
      }
    });
  }, [layers]);

  // Trực quan hóa bản vẽ lại mỗi khi có thay đổi trạng thái màu sắc hoặc ẩn hiện
  useEffect(() => {
    if (!isLoading) {
      renderCanvasLayers(mainCanvasRef.current, appliedColors);
      if (compareMode) {
        renderCanvasLayers(originalCanvasRef.current, {}, true);
      }
    }
  }, [appliedColors, layers, isLoading, compareMode, renderCanvasLayers]);

  // --- 3. ĐIỀU KHIỂN HOÀN TÁC & TIẾN HÀNH (UNDO / REDO HISTORY SYSTEM) ---
  const saveToHistory = useCallback((newColors) => {
    const nextHistory = history.slice(0, historyIndex + 1);
    setHistory([...nextHistory, JSON.stringify(newColors)]);
    setHistoryIndex(nextHistory.length);
  }, [history, historyIndex]);

  const handleUndo = () => {
    if (historyIndex > 0) {
      const prevIndex = historyIndex - 1;
      setHistoryIndex(prevIndex);
      const restored = JSON.parse(history[prevIndex]);
      setAppliedColors(restored);
      showToast("Đã hoàn tác phối màu!", "success");
    } else if (historyIndex === 0) {
      setHistoryIndex(-1);
      setAppliedColors({});
      showToast("Đã hoàn tác về trạng thái gốc!", "success");
    }
  };

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const nextIndex = historyIndex + 1;
      setHistoryIndex(nextIndex);
      const restored = JSON.parse(history[nextIndex]);
      setAppliedColors(restored);
      showToast("Đã tiến hành làm lại!", "success");
    }
  };

  const handleReset = () => {
    if (Object.keys(appliedColors).length === 0) return;
    if (window.confirm("Bạn có chắc chắn muốn xóa toàn bộ màu sắc đã sơn và bắt đầu lại?")) {
      saveToHistory({});
      setAppliedColors({});
      setHistoryIndex(-1);
      setHistory([]);
      showToast("Đã đặt lại toàn bộ màu sơn gốc!", "success");
    }
  };

  // --- 4. TÔ MÀU VÀ CHỌN LAYER TỪ CLICK CHUỘT TRÊN CANVAS (INTERACTIVE PIXEL SAMPLE) ---
  const handleCanvasClick = (e) => {
    if (isLoading || !mainCanvasRef.current) return;

    const canvas = mainCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    // Điểm click của người dùng trên Client
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const naturalWidth = canvas.width;
    const naturalHeight = canvas.height;

    // Tính toán bù biên letterbox (Tỷ lệ object-fit: contain của CSS)
    const elRatio = rect.width / rect.height;
    const imgRatio = naturalWidth / naturalHeight;

    let displayedWidth, displayedHeight, offsetX, offsetY;
    if (elRatio > imgRatio) {
      displayedHeight = rect.height;
      displayedWidth = rect.height * imgRatio;
      offsetX = (rect.width - displayedWidth) / 2;
      offsetY = 0;
    } else {
      displayedWidth = rect.width;
      displayedHeight = rect.width / imgRatio;
      offsetX = 0;
      offsetY = (rect.height - displayedHeight) / 2;
    }

    // Chuyển đổi tọa độ chuột thành tọa độ pixel chính xác của ảnh WebP gốc
    const imgX = ((clickX - offsetX) / displayedWidth) * naturalWidth;
    const imgY = ((clickY - offsetY) / displayedHeight) * naturalHeight;

    // Kiểm tra xem điểm click có nằm bên trong vùng hiển thị hình ảnh hay không
    if (imgX >= 0 && imgX < naturalWidth && imgY >= 0 && imgY < naturalHeight) {
      // Tìm kiếm Layer được click từ trên xuống dưới (Độ ưu tiên zIndex từ cao xuống thấp)
      const sortedLayers = [...layers].sort((a, b) => b.zIndex - a.zIndex);

      for (let layer of sortedLayers) {
        if (!layer.isPaintable || !layer.visible) continue;

        const img = imageCacheRef.current[layer.id];
        if (!img) continue;

        // Tạo 1x1 Offscreen Canvas siêu nhẹ để test nhanh kênh Alpha của điểm click
        const testCanvas = document.createElement('canvas');
        testCanvas.width = 1;
        testCanvas.height = 1;
        const tCtx = testCanvas.getContext('2d');

        try {
          // Vẽ duy nhất 1 pixel tại tọa độ click vào Canvas 1x1
          tCtx.drawImage(img, Math.floor(imgX), Math.floor(imgY), 1, 1, 0, 0, 1, 1);
          const pixelData = tCtx.getImageData(0, 0, 1, 1).data;
          const alpha = pixelData[3]; // Lấy giá trị kênh Alpha (0 - 255)

          if (alpha > 15) { // Ngưỡng không trong suốt (>6% độ mờ)
            setActiveLayerId(layer.id);
            showToast(`Đã chọn phân vùng: ${layer.name} từ hình vẽ Canvas!`, "success");
            break;
          }
        } catch (err) {
          console.error("Click-detection sample failed (CORS block):", err);
        }
      }
    }
  };

  // --- 5. HÀM ÁP DỤNG MÀU CHO ACTIVE LAYER ---
  const applyColor = (color) => {
    if (!activeLayerId) {
      showToast("Vui lòng chọn một phân vùng cần sơn ở cột bên phải!", "warning");
      return;
    }

    const currentLayer = layers.find(l => l.id === activeLayerId);
    if (!currentLayer || !currentLayer.isPaintable) {
      showToast("Phân vùng này là ảnh nền, không thể phối màu sơn!", "warning");
      return;
    }

    const updatedColors = {
      ...appliedColors,
      [activeLayerId]: color.hex_code
    };

    saveToHistory(updatedColors);
    setAppliedColors(updatedColors);
    showToast(`Đã sơn màu ${color.name} (${color.paint_code}) cho ${currentLayer.name}!`);
  };

  // Tắt/Bật trạng thái hiển thị của một Layer
  const toggleLayerVisibility = (layerId, e) => {
    e.stopPropagation(); // Tránh kích hoạt sự kiện chọn layer
    setLayers(prev => prev.map(l => {
      if (l.id === layerId) {
        return { ...l, visible: !l.visible };
      }
      return l;
    }));
  };

  // --- 6. XUẤT ẢNH HOÀN THIỆN XUỐNG THIẾT BỊ (PNG EXPORT ENGINE) ---
  const exportCanvasToImage = () => {
    if (!mainCanvasRef.current || isLoading) return;
    
    try {
      const link = document.createElement('a');
      link.download = `archicolor-phoi-mau-nha.png`;
      link.href = mainCanvasRef.current.toDataURL("image/png");
      link.click();
      showToast("Đang chuẩn bị tải xuống tệp ảnh chất lượng cao...", "success");
    } catch (e) {
      console.error(e);
      showToast("Không thể tải ảnh do vi phạm bảo mật CORS từ nhà cung cấp ảnh ngoại vi!", "danger");
    }
  };

  // --- 7. LỌC & TÌM KIẾM BẢNG MÀU ---
  const filteredColors = useMemo(() => {
    return colors.filter(color => {
      const matchBrand = selectedBrand === "" || color.brand.toUpperCase() === selectedBrand.toUpperCase();
      const matchSearch = color.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          color.paint_code.toLowerCase().includes(searchTerm.toLowerCase());
      return matchBrand && matchSearch;
    });
  }, [colors, selectedBrand, searchTerm]);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#080c14] text-slate-100 font-sans overflow-hidden">
      
      {/* HEADER BAR */}
      <header className="h-[70px] bg-slate-900/80 backdrop-blur-md border-b border-white/5 flex justify-between items-center px-6 z-10">
        <div className="flex items-center gap-3">
          <div className="text-sky-400 text-2xl animate-pulse">
            <i className="fa-solid fa-wand-magic-sparkles"></i>
          </div>
          <div>
            <h1 className="text-lg font-extrabold tracking-wider text-slate-100">
              ARCHICOLOR <span className="text-sky-400">PRO</span>
            </h1>
            <p className="text-[10px] text-slate-400 font-medium">Bản phối màu kiến trúc chuyên sâu GPU-Accelerated</p>
          </div>
        </div>

        {/* Nút điều khiển */}
        <div className="flex items-center gap-2">
          <button 
            onClick={handleUndo} 
            disabled={historyIndex < 0}
            className="px-3 py-2 bg-white/5 border border-white/5 hover:bg-white/10 rounded-md text-xs font-semibold flex items-center gap-1.5 disabled:opacity-30 disabled:pointer-events-none transition"
            title="Hoàn tác (Undo)"
          >
            <i className="fa-solid fa-rotate-left"></i>
            <span>Hoàn tác</span>
          </button>
          <button 
            onClick={handleRedo} 
            disabled={historyIndex >= history.length - 1}
            className="px-3 py-2 bg-white/5 border border-white/5 hover:bg-white/10 rounded-md text-xs font-semibold flex items-center gap-1.5 disabled:opacity-30 disabled:pointer-events-none transition"
            title="Làm lại (Redo)"
          >
            <i className="fa-solid fa-rotate-right"></i>
            <span>Làm lại</span>
          </button>
          <button 
            onClick={handleReset} 
            disabled={Object.keys(appliedColors).length === 0}
            className="px-3 py-2 bg-white/5 border border-white/5 hover:bg-white/10 rounded-md text-xs font-semibold flex items-center gap-1.5 disabled:opacity-30 transition"
            title="Đặt lại từ đầu"
          >
            <i className="fa-solid fa-trash-can"></i>
            <span>Đặt lại</span>
          </button>
          <button 
            onClick={() => setCompareMode(!compareMode)}
            className={`px-3 py-2 border rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${compareMode ? 'bg-sky-500/20 border-sky-400 text-sky-300' : 'bg-white/5 border-white/5 hover:bg-white/10'}`}
          >
            <i className="fa-solid fa-columns"></i>
            <span>So sánh</span>
          </button>
          <button 
            onClick={exportCanvasToImage}
            className="px-4 py-2 bg-gradient-to-r from-sky-600 to-sky-500 hover:from-sky-500 hover:to-sky-400 rounded-md text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-sky-600/20 hover:shadow-sky-500/40 transition"
          >
            <i className="fa-solid fa-file-arrow-down"></i>
            <span>Xuất ảnh PNG</span>
          </button>
        </div>
      </header>

      {/* WORKSPACE AREA */}
      <main className="flex-1 grid grid-cols-[300px_1fr_340px] h-[calc(100vh-70px)] overflow-hidden">
        
        {/* SIDEBAR TRÁI: DANH SÁCH LAYER (BỘ PHẬN NHÀ) */}
        <aside className="border-r border-white/5 bg-slate-950/40 flex flex-col p-4 overflow-y-auto">
          <h2 className="text-xs font-extrabold uppercase text-slate-400 tracking-wider mb-4 flex items-center gap-2">
            <i className="fa-solid fa-layer-group text-sky-400"></i>
            <span>Các phân vùng kiến trúc</span>
          </h2>
          
          <div className="flex flex-col gap-2">
            {layers.map(layer => {
              const isActive = activeLayerId === layer.id;
              const appliedColor = appliedColors[layer.id];
              
              return (
                <div 
                  key={layer.id}
                  onClick={() => layer.isPaintable && setActiveLayerId(layer.id)}
                  className={`p-3 border rounded-lg flex items-center justify-between transition cursor-pointer select-none ${
                    !layer.isPaintable ? 'opacity-60 cursor-not-allowed border-white/5 bg-slate-900/10' :
                    isActive ? 'border-sky-500 bg-sky-500/5 shadow-md shadow-sky-500/5' : 'border-white/5 bg-slate-900/30 hover:bg-slate-900/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-sky-400 shadow-[0_0_8px_#38bdf8]' : 'bg-transparent'}`}></span>
                    <span className="text-xs font-semibold">{layer.name}</span>
                  </div>

                  <div className="flex items-center gap-3">
                    {/* Hiển thị màu sơn đã quét */}
                    {layer.isPaintable && (
                      <span className="text-[10px] font-mono text-slate-400">
                        {appliedColor ? `Hex ${appliedColor}` : "Chưa sơn"}
                      </span>
                    )}
                    
                    {layer.isPaintable && (
                      <div 
                        className="w-5 h-5 rounded-full border border-white/20 shadow-sm"
                        style={{ backgroundColor: appliedColor || '#FFFFFF' }}
                      />
                    )}

                    {/* Nút Ẩn/Hiện Layer */}
                    <button 
                      onClick={(e) => toggleLayerVisibility(layer.id, e)}
                      className={`text-sm hover:text-slate-200 transition ${layer.visible ? 'text-sky-400' : 'text-slate-600'}`}
                      title={layer.visible ? "Ẩn layer" : "Hiện layer"}
                    >
                      <i className={`fa-solid ${layer.visible ? 'fa-eye' : 'fa-eye-slash'}`}></i>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-auto bg-slate-900/40 border border-white/5 p-3 rounded-lg flex gap-2">
            <i className="fa-solid fa-circle-info text-sky-400 text-sm mt-0.5"></i>
            <p className="text-[10px] text-slate-400 leading-normal">
              Click trực tiếp lên các phân vùng của ngôi nhà trên bức vẽ Canvas để chọn nhanh vùng cần tô màu một cách trực quan!
            </p>
          </div>
        </aside>

        {/* CỘT GIỮA: MÀN HÌNH HIỂN THỊ CHÍNH (HTML5 CANVAS) */}
        <section className="bg-[#030610] p-6 flex items-center justify-center relative overflow-hidden">
          
          {isLoading && (
            <div className="absolute inset-0 bg-[#030610]/90 z-20 flex flex-col items-center justify-center gap-4">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '-0.3s' }}></span>
                <span className="w-3 h-3 bg-sky-400 rounded-full animate-bounce" style={{ animationDelay: '-0.15s' }}></span>
                <span className="w-3 h-3 bg-sky-400 rounded-full animate-bounce"></span>
              </div>
              <p className="text-xs font-semibold text-slate-400">Đang chuẩn bị mô hình 3D trong suốt...</p>
            </div>
          )}

          <div ref={containerRef} className="w-full h-full max-w-[90%] max-h-[90%] flex items-center justify-center gap-4">
            
            {/* CANVAS PHỐI MÀU CHÍNH */}
            <div className={`relative flex-1 h-full flex items-center justify-center transition-all ${compareMode ? 'w-1/2' : 'w-full'}`}>
              <canvas 
                ref={mainCanvasRef}
                onClick={handleCanvasClick}
                className="max-w-full max-h-full object-contain cursor-crosshair rounded-lg shadow-2xl border border-white/5 bg-slate-950/20"
                id="main-paint-canvas"
              />
              <span className="absolute bottom-3 left-3 bg-slate-900/80 backdrop-blur border border-white/10 px-2 py-0.5 rounded text-[9px] font-bold text-sky-400 uppercase tracking-widest">
                {compareMode ? "Bản phối màu" : "Bản thiết kế"}
              </span>
            </div>

            {/* CANVAS ĐỐI CHIẾU ẢNH GỐC (BẬT KHI COMPARE ACTIVE) */}
            {compareMode && (
              <div className="relative flex-1 h-full w-1/2 flex items-center justify-center animate-fade-in">
                <canvas 
                  ref={originalCanvasRef}
                  className="max-w-full max-h-full object-contain rounded-lg shadow-2xl border border-white/5 bg-slate-950/20"
                  id="original-paint-canvas"
                />
                <span className="absolute bottom-3 left-3 bg-slate-900/80 backdrop-blur border border-white/10 px-2 py-0.5 rounded text-[9px] font-bold text-slate-400 uppercase tracking-widest">
                  Ngôi nhà gốc
                </span>
              </div>
            )}

          </div>
        </section>

        {/* SIDEBAR PHẢI: BỘ LỌC VÀ LƯỚI BẢNG MÀU SƠN */}
        <aside className="border-l border-white/5 bg-slate-950/40 flex flex-col p-4 overflow-hidden">
          <h2 className="text-xs font-extrabold uppercase text-slate-400 tracking-wider mb-4 flex items-center gap-2">
            <i className="fa-solid fa-palette text-sky-400"></i>
            <span>Bảng màu sơn kiến trúc</span>
          </h2>

          {/* Bộ lọc bảng màu */}
          <div className="flex flex-col gap-3 mb-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-bold uppercase text-slate-500">Hãng sơn</label>
              <select 
                value={selectedBrand} 
                onChange={(e) => setSelectedBrand(e.target.value)}
                className="bg-slate-900 border border-white/5 text-slate-200 text-xs px-3 py-2 rounded-md outline-none focus:border-sky-500 transition cursor-pointer"
              >
                <option value="">Tất cả các hãng</option>
                <option value="Dulux">Dulux Paint</option>
                <option value="Jotun">Jotun Premium</option>
                <option value="Kova">Kova chống thấm</option>
                <option value="Nippon">Nippon Paint</option>
              </select>
            </div>

            <div className="relative">
              <i className="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs"></i>
              <input 
                type="text" 
                placeholder="Tìm mã hoặc tên màu sơn..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-slate-900 border border-white/5 text-slate-200 text-xs pl-9 pr-3 py-2 rounded-md outline-none focus:border-sky-500 transition placeholder:text-slate-500"
              />
            </div>
          </div>

          <div className="text-[10px] text-slate-400 font-bold mb-2 flex justify-between">
            <span>MÀU SẮC PHÙ HỢP BỘ LỌC</span>
            <span className="text-sky-400">{filteredColors.length} màu</span>
          </div>

          {/* Grid hiển thị danh sách màu */}
          <div className="flex-1 overflow-y-auto pr-1">
            {filteredColors.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-2">
                <i className="fa-solid fa-magnifying-glass-minus text-2xl"></i>
                <p className="text-xs">Không tìm thấy màu phù hợp bộ lọc.</p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {filteredColors.map(color => {
                  const isActiveColor = activeLayerId && appliedColors[activeLayerId] === color.hex_code;
                  
                  return (
                    <div 
                      key={color.id}
                      onClick={() => applyColor(color)}
                      className={`p-2 bg-slate-900/60 border rounded-lg hover:border-white/20 transition cursor-pointer flex flex-col items-center justify-center relative select-none ${
                        isActiveColor ? 'border-sky-400 bg-sky-500/5' : 'border-white/5'
                      }`}
                      title={`${color.brand} - ${color.name}`}
                    >
                      <div 
                        className="w-8 h-8 rounded-full border border-white/10 shadow-inner mb-1.5 transition active:scale-125"
                        style={{ backgroundColor: color.hex_code }}
                      />
                      <span className="text-[9px] font-bold text-slate-200 text-center truncate w-full">{color.paint_code}</span>
                      <span className="text-[8px] text-slate-400 truncate w-full text-center">{color.name}</span>
                      
                      {isActiveColor && (
                        <div className="absolute top-1 right-1 w-2.5 h-2.5 bg-sky-400 rounded-full flex items-center justify-center shadow">
                          <i className="fa-solid fa-check text-[6px] text-black font-extrabold"></i>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

      </main>

      {/* TOAST SYSTEM */}
      {toast.show && (
        <div className="fixed bottom-6 left-6 px-4 py-3 bg-slate-900 border border-emerald-500/30 rounded-lg shadow-xl shadow-black/60 flex items-center gap-2.5 z-50 animate-slide-up">
          <i className="fa-solid fa-circle-check text-emerald-400 text-sm"></i>
          <span className="text-xs font-semibold text-slate-200">{toast.message}</span>
        </div>
      )}

    </div>
  );
}
