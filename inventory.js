// 模拟数据库连接
const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:5001'
    : 'https://inventory-count.vercel.app';  // 替换为你的 Vercel 应用 URL

// 设置自动更新间隔（毫秒）
const UPDATE_INTERVAL = 5000;

// 上次更新时间
let lastUpdateTime = null;

// 定义更新间隔变量
let recentHistoryUpdateInterval = null;
let fullHistoryUpdateInterval = null;

// 更新历史记录显示
function updateHistoryDisplay() {
    $.get(`${API_URL}/api/logs`, function(logs) {
        const lang = document.body.className.includes('lang-en') ? 'en' : 'zh';
        
        // 检查是否有新记录
        if (lastUpdateTime) {
            const lastLog = logs[0];
            if (!lastLog || lastLog.timestamp === lastUpdateTime) {
                return; // 没有新记录，不更新显示
            }
        }
        
        lastUpdateTime = logs[0] ? logs[0].timestamp : null;
        
        const html = logs.map(record => {
            const timestamp = new Date(record.timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).replace(/\//g, '-');
            
            return `
            <div class="history-item">
                <div class="time">${timestamp}</div>
                <div class="details">
                    <span class="lang-zh">
                        库位 <span class="bin-code">${record.bin_code}</span>: 
                        商品 <span class="item-code">${record.item_code}</span>
                         <span class="quantity">${record.box_count}</span> 箱 × 
                         <span class="quantity">${record.pieces_per_box}</span> 件/箱 = 
                         <span class="quantity">${record.total_pieces}</span> 件
                    </span>
                    <span class="lang-en">
                        Bin <span class="bin-code">${record.bin_code}</span>: 
                        Item <span class="item-code">${record.item_code}</span>
                        <span class="quantity">${record.box_count}</span> boxes × 
                        <span class="quantity">${record.pieces_per_box}</span> pcs/box = 
                        <span class="quantity">${record.total_pieces}</span> pcs
                    </span>
                </div>
            </div>`;
        }).join('');
        
        const recentHistoryList = document.getElementById('recent-history-list');
        if (recentHistoryList) {
            recentHistoryList.innerHTML = html;
        }
    });
}

// 初始化自动完成功能
$(document).ready(function() {
    console.log("初始化自动完成功能");
    // 商品输入自动完成
    $("#itemInput, #itemSearch, #itemLocationSearch").autocomplete({
        source: function(request, response) {
            console.log("搜索商品:", request.term);
            $.get(`${API_URL}/api/items`, { search: request.term })
                .done(items => {
                    console.log('Items response:', items);
                    response(items.map(item => item.item_code));
                })
                .fail(error => {
                    console.error('Items search error:', error);
                    response([]);  // 返回空数组而不是什么都不做
                });
        },
        minLength: 1,
        delay: 300,  // 添加延迟，避免过于频繁的请求
        autoFocus: true  // 自动聚焦第一个结果
    });

    // 库位输入自动完成
    $("#binInput, #binSearch").autocomplete({
        source: function(request, response) {
            $.get(`${API_URL}/api/bins`, { search: request.term })
                .done(bins => {
                    console.log('Bins response:', bins);
                    response(bins.map(bin => bin.bin_code));
                })
                .fail(error => {
                    console.error('Bins search error:', error);
                    response([]);  // 添加这行
                });
        },
        minLength: 1,
        delay: 300,
        autoFocus: true
    });

    // 页面加载时初始化历史记录显示
    updateHistoryDisplay();
    
    // 设置定时更新
    setInterval(updateHistoryDisplay, UPDATE_INTERVAL);

    // 初始化历史记录更新
    updateRecentHistory();
    if (recentHistoryUpdateInterval) {
        clearInterval(recentHistoryUpdateInterval);
    }
    recentHistoryUpdateInterval = setInterval(updateRecentHistory, 5000);

    // 当切换到历史记录标签页时开始更新
    $('.tab-button[data-tab="history"]').on('click', function() {
        updateFullHistory();
        if (fullHistoryUpdateInterval) {
            clearInterval(fullHistoryUpdateInterval);
        }
        fullHistoryUpdateInterval = setInterval(updateFullHistory, 5000);
    });

    // 当切换离开历史记录标签页时停止更新
    $('.tab-button:not([data-tab="history"])').each(function() {
        $(this).on('click', function() {
            if (fullHistoryUpdateInterval) {
                clearInterval(fullHistoryUpdateInterval);
                fullHistoryUpdateInterval = null;
            }
        });
    });
});

// 提交盘点表单
$("#inventoryForm").submit(function(e) {
    e.preventDefault();
    
    // 移除之前可能存在的事件处理器
    $("#confirm-yes").off('click');
    $("#confirm-no").off('click');
    
    const binCode = $("#binInput").val();
    const itemCode = $("#itemInput").val();
    const boxCount = parseInt($("#boxCount").val());
    const piecesPerBox = parseInt($("#piecesPerBox").val());
    
    // 验证数值
    if (boxCount <= 0 || piecesPerBox <= 0) {
        alert(document.body.className.includes('lang-en') 
            ? "Box count and pieces per box must be greater than 0"
            : "箱数和每箱数量必须大于0");
        return;
    }
    
    // 填充确认对话框
    $("#confirm-bin").text(binCode);
    $("#confirm-item").text(itemCode);
    $("#confirm-box-count").text(boxCount);
    $("#confirm-pieces").text(piecesPerBox);

    // 显示确认对话框
    $("#confirm-dialog").fadeIn(200);

    // 确认按钮事件
    $("#confirm-yes").on('click', function() {
        // 立即移除事件处理器，防止重复提交
        $("#confirm-yes").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
        
        // 在确认后再添加记录
        $.ajax({
            url: `${API_URL}/api/inventory`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                bin_code: binCode,
                item_code: itemCode,
                box_count: boxCount,
                pieces_per_box: piecesPerBox
            }),
            success: function(response) {
                // 成功后再更新显示并重置表单
                setTimeout(updateHistoryDisplay, 100);
                $("#inventoryForm")[0].reset();
            },
            error: function(xhr, status, error) {
                let errorMsg = "添加失败，请检查输入！";
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                alert(errorMsg);
            }
        });
    });

    // 取消按钮事件
    $("#confirm-no").on('click', function() {
        // 移除事件处理器
        $("#confirm-yes").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
    });
});

// 查询商品总数量
function searchItemTotal() {
    const itemCode = $("#itemSearch").val();
    if (!itemCode) {
        $("#itemTotalResult").html(`
            <span class="lang-zh">请输入商品编号！</span>
            <span class="lang-en">Please enter item code!</span>
        `);
        return;
    }
    
    const encodedItemCode = itemCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    const url = `${API_URL}/api/inventory/item/${encodedItemCode}`;
    
    $.ajax({
        url: url,
        type: 'GET',
        success: function(data) {
            // 如果总数为0，显示无库存信息
            if (data.total === 0) {
                $("#itemTotalResult").html(`
                    <div class="result-item">
                        <span class="lang-zh">
                            商品 <span class="item-code">${itemCode}</span> 当前无库存
                        </span>
                        <span class="lang-en">
                            Item <span class="item-code">${itemCode}</span> currently has no inventory
                        </span>
                    </div>
                `);
                return;
            }
            
            $("#itemTotalResult").html(`
                <div class="result-item">
                    <span class="lang-zh">
                        商品 <span class="item-code">${itemCode}</span> 
                        总数量：<span class="quantity">${data.total}</span> 件
                        （<span class="quantity">${data.total_boxes}</span> 箱）
                    </span>
                    <span class="lang-en">
                        Item <span class="item-code">${itemCode}</span> 
                        total quantity: <span class="quantity">${data.total}</span> pcs
                        (<span class="quantity">${data.total_boxes}</span> boxes)
                    </span>
                </div>
            `);
        },
        error: function(xhr, status, error) {
            let errorMsg = {
                zh: "查询失败！",
                en: "Query failed!"
            };
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = {
                    zh: xhr.responseJSON.error,
                    en: xhr.responseJSON.error_en || xhr.responseJSON.error
                };
            }
            $("#itemTotalResult").html(`
                <span class="lang-zh">${errorMsg.zh}</span>
                <span class="lang-en">${errorMsg.en}</span>
            `);
        }
    });
}

// 查询库位内容
function searchBinContents() {
    const binCode = $("#binSearch").val();
    if (!binCode) {
        $("#binContentsResult").html(`
            <span class="lang-zh">请输入库位编号！</span>
            <span class="lang-en">Please enter bin location!</span>
        `);
        return;
    }
    
    const encodedBinCode = binCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    const url = `${API_URL}/api/inventory/bin/${encodedBinCode}`;
    
    $.ajax({
        url: url,
        type: 'GET',
        success: function(contents) {
            if (!contents || contents.length === 0) {
                $("#binContentsResult").html(`
                    <span class="lang-zh">该库位暂无库存</span>
                    <span class="lang-en">No inventory in this location</span>
                `);
                return;
            }
            const html = contents.map(inv => `
                <div class="item-card">
                    <div class="item-header">
                        <span class="lang-zh">
                            商品 <span class="item-code">${inv.item_code}</span>: <span class="quantity">${inv.total_pieces}</span> 件
                        </span>
                        <span class="lang-en">
                            Item <span class="item-code">${inv.item_code}</span>: <span class="quantity">${inv.total_pieces}</span> pcs
                        </span>
                    </div>
                    <div class="box-details-container">
                        ${inv.box_details.sort((a, b) => b.pieces_per_box - a.pieces_per_box).map(detail => `
                            <div class="box-detail-line">
                                <span class="lang-zh">
                                    <span class="quantity">${detail.box_count}</span> 箱 × 
                                    <span class="quantity">${detail.pieces_per_box}</span> 件/箱
                                </span>
                                <span class="lang-en">
                                    <span class="quantity">${detail.box_count}</span> boxes × 
                                    <span class="quantity">${detail.pieces_per_box}</span> pcs/box
                                </span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join("");
            $("#binContentsResult").html(html);
        },
        error: function(xhr, status, error) {
            let errorMsg = "查询失败！";
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            $("#binContentsResult").text(errorMsg);
            console.error("查询失败:", error, xhr.responseText);
        }
    });
}

// 查询商品库位
function searchItemLocations() {
    const itemCode = $("#itemLocationSearch").val();
    if (!itemCode) {
        $("#itemLocationsResult").html(`
            <span class="lang-zh">请输入商品编号！</span>
            <span class="lang-en">Please enter item code!</span>
        `);
        return;
    }
    
    const encodedItemCode = itemCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    
    $.ajax({
        url: `${API_URL}/api/inventory/locations/${encodedItemCode}`,
        type: 'GET',
        success: function(locations) {
            if (!locations || locations.length === 0) {
                $("#itemLocationsResult").html(`
                    <span class="lang-zh">未找到该商品</span>
                    <span class="lang-en">Item not found</span>
                `);
                return;
            }
            const html = locations.map(loc => `
                <div class="item-card">
                    <div class="item-header">
                        <span class="lang-zh">
                            库位 <span class="bin-code">${loc.bin_code}</span>: <span class="quantity">${loc.total_pieces}</span> 件
                        </span>
                        <span class="lang-en">
                            Bin <span class="bin-code">${loc.bin_code}</span>: <span class="quantity">${loc.total_pieces}</span> pcs
                        </span>
                    </div>
                    <div class="box-details-container">
                        ${loc.box_details.sort((a, b) => b.pieces_per_box - a.pieces_per_box).map(detail => `
                            <div class="box-detail-line">
                                <span class="lang-zh">
                                    <span class="quantity">${detail.box_count}</span> 箱 × 
                                    <span class="quantity">${detail.pieces_per_box}</span> 件/箱
                                </span>
                                <span class="lang-en">
                                    <span class="quantity">${detail.box_count}</span> boxes × 
                                    <span class="quantity">${detail.pieces_per_box}</span> pcs/box
                                </span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join("");
            $("#itemLocationsResult").html(html);
        },
        error: function(xhr, status, error) {
            let errorMsg = "查询失败！";
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            $("#itemLocationsResult").text(errorMsg);
            console.error("查询失败:", error, xhr.responseText);
        }
    });
}

// 导出商品库存
function exportItems() {
    window.location.href = `${API_URL}/api/export/items`;
}

// 导出库位库存
function exportBins() {
    window.location.href = `${API_URL}/api/export/bins`;
}

// 语言切换时更新历史记录显示
function switchLanguage(lang) {
    document.body.className = 'lang-' + lang;
    localStorage.setItem('preferred-language', lang);
    // 更新按钮状态
    $('.language-switch button').removeClass('active');
    $(`.language-switch button[onclick="switchLanguage('${lang}')"]`).addClass('active');
    // 更新历史记录显示
    updateHistoryDisplay();
}

// 查询标签页切换
function switchQueryTab(tabId) {
    $('.query-content').removeClass('active');
    $('.query-tab-button').removeClass('active');
    $(`#${tabId}-tab`).addClass('active');
    $(`.query-tab-button[data-tab="${tabId}"]`).addClass('active');
}

// 更新最近5条历史记录
function updateRecentHistory() {
    $.get(`${API_URL}/api/logs`, function(logs) {
        const recentLogs = logs.slice(0, 5);  // 只取最近5条
        const html = recentLogs.map(record => {
            const timestamp = new Date(record.timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).replace(/\//g, '-');
            
            return `
            <div class="history-item">
                <div class="time">${timestamp}</div>
                <div class="details">
                    <span class="lang-zh">
                        库位 <span class="bin-code">${record.bin_code}</span>: 
                        商品 <span class="item-code">${record.item_code}</span>
                         <span class="quantity">${record.box_count}</span> 箱 × 
                         <span class="quantity">${record.pieces_per_box}</span> 件/箱 = 
                         <span class="quantity">${record.total_pieces}</span> 件
                    </span>
                    <span class="lang-en">
                        Bin <span class="bin-code">${record.bin_code}</span>: 
                        Item <span class="item-code">${record.item_code}</span>
                        <span class="quantity">${record.box_count}</span> boxes × 
                        <span class="quantity">${record.pieces_per_box}</span> pcs/box = 
                        <span class="quantity">${record.total_pieces}</span> pcs
                    </span>
                </div>
            </div>`;
        }).join('');
        
        const recentHistoryList = document.getElementById('recent-history-list');
        if (recentHistoryList) {
            recentHistoryList.innerHTML = html;
        }
    });
}

// 更新完整历史记录
function updateFullHistory() {
    $.get(`${API_URL}/api/logs`, function(logs) {
        const html = logs.map(record => {
            const timestamp = new Date(record.timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).replace(/\//g, '-');
            
            return `
            <div class="history-item">
                <div class="time">${timestamp}</div>
                <div class="details">
                    <span class="lang-zh">
                        库位 <span class="bin-code">${record.bin_code}</span>: 
                        商品 <span class="item-code">${record.item_code}</span>
                         <span class="quantity">${record.box_count}</span> 箱 × 
                         <span class="quantity">${record.pieces_per_box}</span> 件/箱 = 
                         <span class="quantity">${record.total_pieces}</span> 件
                    </span>
                    <span class="lang-en">
                        Bin <span class="bin-code">${record.bin_code}</span>: 
                        Item <span class="item-code">${record.item_code}</span>
                        <span class="quantity">${record.box_count}</span> boxes × 
                        <span class="quantity">${record.pieces_per_box}</span> pcs/box = 
                        <span class="quantity">${record.total_pieces}</span> pcs
                    </span>
                </div>
            </div>`;
        }).join('');
        
        const fullHistoryList = document.getElementById('full-history-list');
        if (fullHistoryList) {
            fullHistoryList.innerHTML = html;
        }
    });
} 