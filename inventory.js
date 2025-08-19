// 模拟数据库连接
function getApiUrl() {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:5001';
    } else if (hostname.includes('railway.app')) {
        return 'https://sohoapparelwarehouse.up.railway.app';
    } else {
        return 'https://inventorycount-production.up.railway.app';
    }
}

const API_URL = getApiUrl();

// 设置自动更新间隔（毫秒）
const UPDATE_INTERVAL = 5000;

// 上次更新时间
let lastUpdateTime = null;

// 缓存最近一次获取的日志，语言切换时直接使用本地渲染以避免重复网络请求
let cachedLogs = [];

// 定义更新间隔变量
let recentHistoryUpdateInterval = null;
let fullHistoryUpdateInterval = null;

// 跟踪用户选择的日期
let userSelectedDate = null;

// 合并“清空并添加”的历史记录（将紧邻的 清空库位 + 添加 组合为一条）
function mergeClearAndAddLogs(logs) {
    if (!Array.isArray(logs) || logs.length === 0) return [];
    const result = [];
    const usedIndexSet = new Set();
    const isClear = (code) => code === '清空库位' || code === 'Clear Bin';
    const withinMs = 5000; // 允许合并的最大时间差（毫秒）

    for (let i = 0; i < logs.length; i++) {
        if (usedIndexSet.has(i)) continue;
        const current = logs[i];

        // 优先尝试与下一条合并，避免重复扫描
        const j = i + 1;
        if (j < logs.length && !usedIndexSet.has(j)) {
            const next = logs[j];
            const sameBin = current.bin_code === next.bin_code;
            const timeA = new Date(current.timestamp).getTime();
            const timeB = new Date(next.timestamp).getTime();
            const closeInTime = Math.abs(timeA - timeB) <= withinMs;

            // 情况1：按时间倒序常见，先看到添加，后一条是清空
            if (!isClear(current.item_code) && isClear(next.item_code) && sameBin && closeInTime) {
                result.push({
                    __merged: true,
                    bin_code: current.bin_code,
                    item_code: current.item_code,
                    box_count: current.box_count,
                    pieces_per_box: current.pieces_per_box,
                    total_pieces: current.total_pieces,
                    timestamp: current.timestamp
                });
                usedIndexSet.add(i);
                usedIndexSet.add(j);
                continue;
            }

            // 情况2：先看到清空，后一条是添加（边界情况）
            if (isClear(current.item_code) && !isClear(next.item_code) && sameBin && closeInTime) {
                result.push({
                    __merged: true,
                    bin_code: next.bin_code,
                    item_code: next.item_code,
                    box_count: next.box_count,
                    pieces_per_box: next.pieces_per_box,
                    total_pieces: next.total_pieces,
                    timestamp: timeA >= timeB ? current.timestamp : next.timestamp
                });
                usedIndexSet.add(i);
                usedIndexSet.add(j);
                continue;
            }
        }

        // 无法合并则原样放入
        result.push(current);
        usedIndexSet.add(i);
    }

    return result;
}

// 格式化历史记录显示
function formatHistoryRecord(record, timestamp, lang) {
    const isZh = lang === 'zh';
    
    let lineHtml;
    
    if (record.__merged) {
        // 清空并添加的合并记录
        const mergedZh = `🗑️ 清空库位后添加：库位 <span class="bin-code">${record.bin_code}</span>: 商品 <span class="item-code">${record.item_code}</span> (${record.box_count} 箱 × ${record.pieces_per_box} 件/箱 = ${record.total_pieces} 件) 来自 BT: <span class="BT-number">${record.BT || 'N/A'}</span> 添加到库位: <span class="bin-code">${record.bin_code}</span>`;
        const mergedEn = `🗑️ Cleared then added: Item: <span class="item-code">${record.item_code}</span> (${record.box_count} boxes × ${record.pieces_per_box} pcs/box = ${record.total_pieces} pcs) from BT: <span class="BT-number">${record.BT || 'N/A'}</span> added at Bin: <span class="bin-code">${record.bin_code}</span>`;
        lineHtml = isZh ? mergedZh : mergedEn;
    } else if (record.item_code === '清空库位' || record.item_code === 'Clear Bin') {
        // 清空bin
        const clearZh = `🗑️ 清空库位: <span class="bin-code">${record.bin_code}</span> cleared`;
        const clearEn = `🗑️ Bin: <span class="bin-code">${record.bin_code}</span> cleared`;
        lineHtml = isZh ? clearZh : clearEn;
    } else if (record.item_code && record.item_code.startsWith('清空商品')) {
        // 清空item
        const itemCode = record.item_code.replace('清空商品', '');
        const clearItemZh = `🗑️ 清空商品: 商品: <span class="item-code">${itemCode}</span> 来自 BT: <span class="BT-number">${record.BT || 'N/A'}</span> 在库位: <span class="bin-code">${record.bin_code}</span> 清空`;
        const clearItemEn = `🗑️ Item: <span class="item-code">${itemCode}</span> from BT: <span class="BT-number">${record.BT || 'N/A'}</span> cleared at Bin: <span class="bin-code">${record.bin_code}</span>`;
        lineHtml = isZh ? clearItemZh : clearItemEn;
    } else {
        // 普通input记录
        const normalZh = `商品: <span class="item-code">${record.item_code}</span> (${record.box_count} 箱 × ${record.pieces_per_box} 件/箱 = ${record.total_pieces} 件) 来自 BT: <span class="BT-number">${record.BT || 'N/A'}</span> 添加到库位: <span class="bin-code">${record.bin_code}</span>`;
        const normalEn = `Item: <span class="item-code">${record.item_code}</span> (${record.box_count} boxes × ${record.pieces_per_box} pcs/box = ${record.total_pieces} pcs) from BT: <span class="BT-number">${record.BT || 'N/A'}</span> added at Bin: <span class="bin-code">${record.bin_code}</span>`;
        lineHtml = isZh ? normalZh : normalEn;
    }

    return `
    <div class="history-item">
        <div class="time">${timestamp}</div>
        <div class="details">${lineHtml}</div>
    </div>`;
}

// 更新历史记录显示
function updateHistoryDisplay(logsFromCache) {
    const render = (logs) => {
        const lang = document.body.className.includes('lang-en') ? 'en' : 'zh';
        
        // 检查是否有新记录
        if (lastUpdateTime) {
            const lastLog = logs[0];
            if (!lastLog || lastLog.timestamp === lastUpdateTime) {
                return; // 没有新记录，不更新显示
            }
        }
        
        lastUpdateTime = logs[0] ? logs[0].timestamp : null;
        
        const mergedLogs = mergeClearAndAddLogs(logs);
        const html = mergedLogs.map(record => {
            const timestamp = new Date(record.timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).replace(/\//g, '-');
            return formatHistoryRecord(record, timestamp, lang);
        }).join('');
        
        const recentHistoryList = document.getElementById('recent-history-list');
        if (recentHistoryList) {
            recentHistoryList.innerHTML = html;
        }
    };

    if (logsFromCache && logsFromCache.length) {
        render(logsFromCache);
        return;
    }

    $.get(`${API_URL}/api/logs`, function(logs) {
        cachedLogs = logs;
        render(logs);
    });
}

// 初始化自动完成功能
$(document).ready(function() {
    console.log("初始化自动完成功能");
    // 商品输入自动完成（仅搜索功能）
    $("#itemSearch, #itemLocationSearch").autocomplete({
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

    // BT输入自动完成
    $("#BTSearch").autocomplete({
        source: function(request, response) {
            $.get(`${API_URL}/api/BTs`, { search: request.term })
                .done(BTs => {
                    console.log('BTs response:', BTs);
                    response(BTs.map(BT => BT.BT));
                })
                .fail(error => {
                    console.error('BTs search error:', error);
                    response([]);
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
        // 设置今天日期为默认值
        const today = new Date().toISOString().split('T')[0];
        $("#historyDate").val(today);
        showTodayHistory();
        if (fullHistoryUpdateInterval) {
            clearInterval(fullHistoryUpdateInterval);
        }
        // 使用自定义的定时器函数，保持当前选择的日期
        fullHistoryUpdateInterval = setInterval(function() {
            if (userSelectedDate) {
                // 如果用户选择了日期，继续使用该日期
                filterHistoryByDate();
            } else {
                // 否则显示所有记录
                updateFullHistory();
            }
        }, 5000);
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

    // 初始化搜索框占位符 - 延迟执行确保语言已设置
    setTimeout(() => {
        const savedLang = localStorage.getItem('preferred-language') || 'zh';
        updateSearchPlaceholders(savedLang);
    }, 100);
});

// 提交盘点表单
$("#inventoryForm").submit(function(e) {
    e.preventDefault();
    
    // 移除之前可能存在的事件处理器
    $("#confirm-yes").off('click');
    $("#confirm-no").off('click');
    
    const binCode = $("#binInput").val();
    const itemCode = $("#itemInput").val();
    const BTNumber = $("#BTInput").val();
    const boxCount = parseInt($("#boxCount").val());
    const piecesPerBox = parseInt($("#piecesPerBox").val());
    
    // 验证数值
    if (boxCount <= 0 || piecesPerBox <= 0) {
        alert(document.body.className.includes('lang-en') 
            ? "Box count and pieces per box must be greater than 0"
            : "箱数和每箱数量必须大于0");
        return;
    }
    
    // 先检查库位状态
    checkBinStatus(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
});

// 检查库位状态并显示相应的确认对话框
function checkBinStatus(binCode, itemCode, BTNumber, boxCount, piecesPerBox) {
    const encodedBinCode = binCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    
    $.ajax({
        url: `${API_URL}/api/inventory/bin/${encodedBinCode}`,
        type: 'GET',
        success: function(contents) {
            if (contents && contents.length > 0) {
                // 库位有库存，显示选择对话框
                showBinChoiceDialog(binCode, itemCode, BTNumber, boxCount, piecesPerBox, contents);
            } else {
                // 库位为空，直接显示确认对话框
                showConfirmDialog(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
            }
        },
        error: function(xhr, status, error) {
            // 如果查询失败，直接显示确认对话框
            showConfirmDialog(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
        }
    });
}

// 显示库位选择对话框
function showBinChoiceDialog(binCode, itemCode, BTNumber, boxCount, piecesPerBox, existingContents) {
    // 移除之前可能存在的事件处理器
    $("#confirm-yes").off('click');
    $("#confirm-no").off('click');
    
    // 修改确认对话框标题
    $("#confirm-dialog h3 .lang-zh").text('库位已有库存，请选择操作方式');
    $("#confirm-dialog h3 .lang-en").text('Bin has existing inventory, please choose action');
    
    // 创建现有库存详情HTML
    let existingHtml = '';
    existingContents.forEach(inv => {
        existingHtml += `
            <div class="confirm-item">
                <div class="item-header">
                    <span class="lang-zh">
                        商品 <span class="item-code">${inv.item_code}</span>: 
                        <span class="quantity">${inv.total_pieces}</span> 件
                    </span>
                    <span class="lang-en">
                        Item <span class="item-code">${inv.item_code}</span>: 
                        <span class="quantity">${inv.total_pieces}</span> pcs
                    </span>
                </div>
                <div class="box-details">
                    ${inv.box_details.sort((a, b) => b.pieces_per_box - a.pieces_per_box)
                        .map(detail => `
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
        `;
    });
    
    // 填充确认对话框
    $(".confirm-details").html(`
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">库位：</span>
                <span class="lang-en">Bin:</span>
            </span>
            <span class="bin-code">${binCode}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">新商品：</span>
                <span class="lang-en">New Item:</span>
            </span>
            <span class="item-code">${itemCode}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">BT：</span>
                <span class="lang-en">BT:</span>
            </span>
            <span class="BT-number">${BTNumber || '-'}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">新库存：</span>
                <span class="lang-en">New Inventory:</span>
            </span>
            <span class="quantity">${boxCount} 箱 × ${piecesPerBox} 件/箱 = ${boxCount * piecesPerBox} 件</span>
        </div>
        <div class="inventory-details">
            <div class="confirm-item">
                <div class="item-header">
                    <span class="lang-zh">现有库存：</span>
                    <span class="lang-en">Existing Inventory:</span>
                </div>
                ${existingHtml}
            </div>
        </div>
    `);
    
    // 修改按钮显示和样式
    $("#confirm-yes").removeClass('confirm').addClass('success');
    $("#confirm-yes .lang-zh").text('直接添加');
    $("#confirm-yes .lang-en").text('Add Directly');
    
    $("#confirm-middle").show();
    $("#confirm-middle .lang-zh").text('清空库位后添加');
    $("#confirm-middle .lang-en").text('Clear and Add');
    
    $("#confirm-no").removeClass('cancel').addClass('cancel');
    $("#confirm-no .lang-zh").text('取消');
    $("#confirm-no .lang-en").text('Cancel');
    
    // 显示确认对话框
    $("#confirm-dialog").fadeIn(200);
    
    // 确认按钮事件 - 直接添加
    $("#confirm-yes").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
        
        // 直接添加新库存
        addInventory(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
    });
    
    // 中间按钮事件 - 清空库位后添加
    $("#confirm-middle").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
        
        // 先清空库位，然后添加新库存
        clearBinAndAdd(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
    });
    
    // 取消按钮事件
    $("#confirm-no").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
    });
}

// 显示普通确认对话框
function showConfirmDialog(binCode, itemCode, BTNumber, boxCount, piecesPerBox) {
    // 移除之前可能存在的事件处理器
    $("#confirm-yes").off('click');
    $("#confirm-no").off('click');
    
    // 重置确认对话框标题
    $("#confirm-dialog h3 .lang-zh").text('请确认输入信息');
    $("#confirm-dialog h3 .lang-en").text('Please Confirm Input');
    
    // 填充确认对话框
    $(".confirm-details").html(`
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">库位：</span>
                <span class="lang-en">Bin:</span>
            </span>
            <span id="confirm-bin" class="bin-code">${binCode}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">商品：</span>
                <span class="lang-en">Item:</span>
            </span>
            <span id="confirm-item" class="item-code">${itemCode}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">BT：</span>
                <span class="lang-en">BT:</span>
            </span>
            <span id="confirm-BT" class="BT-number">${BTNumber || '-'}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">箱数：</span>
                <span class="lang-en">Box Count:</span>
            </span>
            <span id="confirm-box-count" class="quantity">${boxCount}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">每箱数量：</span>
                <span class="lang-en">Pieces per Box:</span>
            </span>
            <span id="confirm-pieces" class="quantity">${piecesPerBox}</span>
        </div>
    `);
    
    // 重置按钮显示和样式
    $("#confirm-yes").removeClass('success').addClass('confirm');
    $("#confirm-yes .lang-zh").text('确认');
    $("#confirm-yes .lang-en").text('Confirm');
    
    $("#confirm-middle").hide();
    
    $("#confirm-no").removeClass('cancel').addClass('cancel');
    $("#confirm-no .lang-zh").text('取消');
    $("#confirm-no .lang-en").text('Cancel');
    
    // 显示确认对话框
    $("#confirm-dialog").fadeIn(200);
    
    // 确认按钮事件
    $("#confirm-yes").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
        
        // 添加库存
        addInventory(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
    });
    
    // 取消按钮事件
    $("#confirm-no").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
    });
}

// 清空库位后添加新库存
function clearBinAndAdd(binCode, itemCode, BTNumber, boxCount, piecesPerBox) {
    const encodedBinCode = binCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    
    $.ajax({
        url: `${API_URL}/api/inventory/bin/${encodedBinCode}/clear`,
        type: 'DELETE',
        success: function(response) {
            // 清空成功后添加新库存
            addInventory(binCode, itemCode, BTNumber, boxCount, piecesPerBox);
        },
        error: function(xhr, status, error) {
            alert(document.body.className.includes('lang-en')
                ? "Failed to clear bin, please try again"
                : "清空库位失败，请重试");
        }
    });
}

// 添加库存
function addInventory(binCode, itemCode, BTNumber, boxCount, piecesPerBox) {
    $.ajax({
        url: `${API_URL}/api/inventory`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            bin_code: binCode,
            item_code: itemCode,
            BT: BTNumber,
            box_count: boxCount,
            pieces_per_box: piecesPerBox
        }),
        success: function(response) {
            // 成功后再更新显示并重置表单
            setTimeout(updateHistoryDisplay, 100);
            
            // 重置表单（包括BT输入框）
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
}

// 查询商品总数量和所在库位
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
    
    // 同时获取总数量和库位信息
    $.when(
        $.get(`${API_URL}/api/inventory/item/${encodedItemCode}`),
        $.get(`${API_URL}/api/inventory/locations/${encodedItemCode}`)
    ).done(function(totalData, locationsData) {
        const total = totalData[0];
        const locations = locationsData[0];
        
        // 如果总数为0，显示无库存信息
        if (total.total === 0) {
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
        
        // 构建总数量信息
        let html = `
            <div class="result-item">
                <div class="total-summary">
                    <span class="lang-zh">
                        商品 <span class="item-code">${itemCode}</span> 
                        总数量：<span class="quantity">${total.total}</span> 件
                        （<span class="quantity">${total.total_boxes}</span> 箱）
                    </span>
                    <span class="lang-en">
                        Item <span class="item-code">${itemCode}</span> 
                        total quantity: <span class="quantity">${total.total}</span> pcs
                        (<span class="quantity">${total.total_boxes}</span> boxes)
                    </span>
                </div>
        `;
        
        // 添加库位详细信息
        if (locations && locations.length > 0) {
            html += `
                <div class="locations-details">
                    <h4>
                        <span class="lang-zh">所在库位：</span>
                        <span class="lang-en">Locations:</span>
                    </h4>
                    ${locations.map(loc => `
                        <div class="item-card">
                            <div class="item-header">
                                <div class="location-info">
                                    <span class="lang-zh">
                                        库位 <span class="bin-code">${loc.bin_code}</span>: <span class="quantity">${loc.total_pieces}</span> 件
                                        ${loc.BT ? ` (BT: <span class="BT-number">${loc.BT}</span>)` : ''}
                                    </span>
                                    <span class="lang-en">
                                        Bin <span class="bin-code">${loc.bin_code}</span>: <span class="quantity">${loc.total_pieces}</span> pcs
                                        ${loc.BT ? ` (BT: <span class="BT-number">${loc.BT}</span>)` : ''}
                                    </span>
                                </div>
                            </div>
                            <div class="box-details-BT">
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
                    `).join("")}
                </div>
            `;
        }
        
        html += '</div>';
        $("#itemTotalResult").html(html);
        
    }).fail(function(xhr, status, error) {
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
            // 添加清除按钮
            let html = `
                <div class="bin-header">
                    <h3>
                        <span class="lang-zh">库位: <span class="bin-code">${binCode}</span></span>
                        <span class="lang-en">Bin: <span class="bin-code">${binCode}</span></span>
                    </h3>
                    <button class="clear-bin-button" onclick="clearBinInventory('${binCode}')">
                        <span class="lang-zh">清空库位</span>
                        <span class="lang-en">Clear Bin</span>
                    </button>
                </div>
            `;
            
            if (!contents || contents.length === 0) {
                html += `
                    <span class="lang-zh">该库位暂无库存</span>
                    <span class="lang-en">No inventory in this location</span>
                `;
                $("#binContentsResult").html(html);
                return;
            }
            
            html += contents.map(inv => `
                <div class="item-card">
                    <div class="item-header">
                        <div class="item-info">
                            <span class="lang-zh">
                                商品 <span class="item-code">${inv.item_code}</span>: <span class="quantity">${inv.total_pieces}</span> 件
                            </span>
                            <span class="lang-en">
                                Item <span class="item-code">${inv.item_code}</span>: <span class="quantity">${inv.total_pieces}</span> pcs
                            </span>
                        </div>
                        <button class="clear-item-button" onclick="clearItemAtBin('${binCode}', '${inv.item_code}')">
                            <span class="lang-zh">清空此商品</span>
                            <span class="lang-en">Clear Item</span>
                        </button>
                    </div>
                    <div class="box-details-BT">
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



// 导出商品库存
function exportItems() {
    window.location.href = `${API_URL}/api/export/items`;
}

// 导出库位库存
function exportBins() {
    window.location.href = `${API_URL}/api/export/bins`;
}

// 导出商品明细
function exportItemDetails() {
    window.location.href = `${API_URL}/api/export/item-details`;
}

// 显示今天的历史记录
function showTodayHistory() {
    const today = new Date().toISOString().split('T')[0];
    $("#historyDate").val(today);
    userSelectedDate = today; // 设置用户选择的日期为今天
    filterHistoryByDate();
}

// 根据日期过滤历史记录
function filterHistoryByDate() {
    const selectedDate = $("#historyDate").val();
    if (!selectedDate) {
        userSelectedDate = null;
        updateFullHistory();
        return;
    }
    
    // 设置用户选择的日期
    userSelectedDate = selectedDate;
    
    $.ajax({
        url: `${API_URL}/api/logs`,
        type: 'GET',
        data: { date: selectedDate },
        success: function(logs) {
            cachedLogs = logs;
            renderFilteredHistory(logs, selectedDate);
        },
        error: function(xhr, status, error) {
            console.error('Error fetching filtered history:', error);
            $("#full-history-list").html(`
                <span class="lang-zh">获取历史记录失败！</span>
                <span class="lang-en">Failed to fetch history!</span>
            `);
        }
    });
}

// 渲染过滤后的历史记录
function renderFilteredHistory(logs, date) {
    const isZh = document.body.className.includes('lang-zh');
    const lang = isZh ? 'zh' : 'en';
    
    if (!logs || logs.length === 0) {
        const noDataMsg = isZh ? 
            `没有找到 ${date} 的历史记录` : 
            `No history records found for ${date}`;
        $("#full-history-list").html(`<div class="no-data">${noDataMsg}</div>`);
        return;
    }
    
    // 合并清空并添加的记录
    const mergedLogs = mergeClearAndAddLogs(logs);
    
    let html = '';
    mergedLogs.forEach(record => {
        const timestamp = new Date(record.timestamp).toLocaleString(isZh ? 'zh-CN' : 'en-US');
        html += formatHistoryRecord(record, timestamp, lang);
    });
    
    $("#full-history-list").html(html);
}

// 导出指定日期的历史记录
function exportHistoryByDate() {
    const selectedDate = $("#historyDate").val();
    if (!selectedDate) {
        alert(document.body.className.includes('lang-en') ? 
            "Please select a date first!" : 
            "请先选择日期！");
        return;
    }
    
    window.open(`${API_URL}/api/export/history?date=${selectedDate}`, '_blank');
}

// 导出全部历史记录
function exportAllHistory() {
    window.open(`${API_URL}/api/export/history`, '_blank');
}

    // 搜索BT
function searchBT() {
    const BTNumber = $("#BTSearch").val();
    if (!BTNumber) {
        $("#BTSearchResult").html(`
            <span class="lang-zh">请输入BT号！</span>
            <span class="lang-en">Please enter BT number!</span>
        `);
        return;
    }
    
    $.ajax({
        url: `${API_URL}/api/inventory/BT/${encodeURIComponent(BTNumber)}`,
        type: 'GET',
        success: function(data) {
            if (!data.items || data.items.length === 0) {
                $("#BTSearchResult").html(`
                    <div class="result-item">
                        <span class="lang-zh">
                            BT <span class="BT-number">${BTNumber}</span> 中暂无商品
                        </span>
                        <span class="lang-en">
                            BT <span class="BT-number">${BTNumber}</span> has no items
                        </span>
                    </div>
                `);
                return;
            }
            
            // 构建总数量信息
            let html = `
                <div class="result-item">
                    <div class="total-summary">
                        <span class="lang-zh">
                            BT <span class="BT-number">${BTNumber}</span> 
                            总商品数：<span class="quantity">${data.total_items}</span> 种
                            总数量：<span class="quantity">${data.total_pieces}</span> 件
                        </span>
                        <span class="lang-en">
                            BT <span class="BT-number">${BTNumber}</span> 
                            total items: <span class="quantity">${data.total_items}</span> types
                            total quantity: <span class="quantity">${data.total_pieces}</span> pcs
                        </span>
                    </div>
                    <div class="items-details">
                        <h4>
                            <span class="lang-zh">商品明细：</span>
                            <span class="lang-en">Item Details:</span>
                        </h4>
                        ${data.items.map(item => `
                            <div class="item-card">
                                <div class="item-header">
                                    <div class="item-info">
                                        <span class="lang-zh">
                                            商品 <span class="item-code">${item.item_code}</span>: <span class="quantity">${item.total_pieces}</span> 件
                                        </span>
                                        <span class="lang-en">
                                            Item <span class="item-code">${item.item_code}</span>: <span class="quantity">${item.total_pieces}</span> pcs
                                        </span>
                                    </div>
                                </div>
                                <div class="locations-details">
                                    <span class="lang-zh">所在库位：</span>
                                    <span class="lang-en">Locations:</span>
                                    ${item.locations.map(loc => `
                                        <div class="location-item">
                                            <span class="lang-zh">
                                                库位 <span class="bin-code">${loc.bin_code}</span>: <span class="quantity">${loc.pieces}</span> 件
                                            </span>
                                            <span class="lang-en">
                                                Bin <span class="bin-code">${loc.bin_code}</span>: <span class="quantity">${loc.pieces}</span> pcs
                                            </span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `;
            
            $("#BTSearchResult").html(html);
        },
        error: function(xhr, status, error) {
            let errorMsg = {
                zh: "搜索失败！",
                en: "Search failed!"
            };
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = {
                    zh: xhr.responseJSON.error,
                    en: xhr.responseJSON.error_en || xhr.responseJSON.error
                };
            }
            $("#BTSearchResult").html(`
                <span class="lang-zh">${errorMsg.zh}</span>
                <span class="lang-en">${errorMsg.en}</span>
            `);
        }
    });
}

// 导出数据库
function exportDatabase() {
    window.location.href = `${API_URL}/api/export/database`;
}

// 语言切换时更新历史记录显示
function switchLanguage(lang) {
    document.body.className = 'lang-' + lang;
    localStorage.setItem('preferred-language', lang);
    // 更新按钮状态
    $('.language-switch button').removeClass('active');
    $(`.language-switch button[onclick="switchLanguage('${lang}')"]`).addClass('active');
    
    // 更新搜索框占位符
    updateSearchPlaceholders(lang);
    
    // 使用缓存立即重渲染，避免重复请求
    updateHistoryDisplay(cachedLogs);
    updateRecentHistory(cachedLogs);
    updateFullHistory(cachedLogs);
}

// 更新搜索框占位符
function updateSearchPlaceholders(lang) {
            const placeholders = {
            zh: {
                binSearch: '输入库位编号',
                BTSearch: '输入BT号',
                itemSearch: '输入商品编号'
            },
            en: {
                binSearch: 'Enter bin location',
                BTSearch: 'Enter BT number',
                itemSearch: 'Enter item code'
            }
        };
    
    const texts = placeholders[lang];
    $('#binSearch').attr('placeholder', texts.binSearch);
    $('#BTSearch').attr('placeholder', texts.BTSearch);
    $('#itemSearch').attr('placeholder', texts.itemSearch);
}

// 查询标签页切换
function switchQueryTab(tabId) {
    $('.query-content').removeClass('active');
    $('.query-tab-button').removeClass('active');
    $(`#${tabId}-tab`).addClass('active');
    $(`.query-tab-button[data-tab="${tabId}"]`).addClass('active');
}

// 更新今日录入记录
function updateRecentHistory(logsFromCache) {
    const render = (logs) => {
        const mergedLogs = mergeClearAndAddLogs(logs);
        
        // 获取今日日期（使用本地时区）
        const today = new Date();
        const todayStr = today.getFullYear() + '-' + 
                        String(today.getMonth() + 1).padStart(2, '0') + '-' + 
                        String(today.getDate()).padStart(2, '0');
        
        // 过滤出今日的记录（使用本地时区）
        const todayLogs = mergedLogs.filter(record => {
            const recordDate = new Date(record.timestamp);
            const recordDateStr = recordDate.getFullYear() + '-' + 
                                 String(recordDate.getMonth() + 1).padStart(2, '0') + '-' + 
                                 String(recordDate.getDate()).padStart(2, '0');
            return recordDateStr === todayStr;
        });
        
        const html = todayLogs.map(record => {
            const timestamp = new Date(record.timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).replace(/\//g, '-');
            return formatHistoryRecord(record, timestamp, document.body.className.includes('lang-en') ? 'en' : 'zh');
        }).join('');
        
        const recentHistoryList = document.getElementById('recent-history-list');
        if (recentHistoryList) {
            if (todayLogs.length === 0) {
                const lang = document.body.className.includes('lang-en') ? 'en' : 'zh';
                const noDataText = lang === 'zh' ? '今日暂无录入记录' : 'No input records today';
                recentHistoryList.innerHTML = `<div style="text-align: center; color: #666; padding: 20px;">${noDataText}</div>`;
            } else {
                recentHistoryList.innerHTML = html;
            }
        }
    };

    if (logsFromCache && logsFromCache.length) {
        render(logsFromCache);
        return;
    }

    $.get(`${API_URL}/api/logs`, function(logs) {
        cachedLogs = logs;
        render(logs);
    });
}

// 更新完整历史记录
function updateFullHistory(logsFromCache) {
    const render = (logs) => {
        const mergedLogs = mergeClearAndAddLogs(logs);
        const html = mergedLogs.map(record => {
            const timestamp = new Date(record.timestamp).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).replace(/\//g, '-');
            return formatHistoryRecord(record, timestamp, document.body.className.includes('lang-en') ? 'en' : 'zh');
        }).join('');
        
        const fullHistoryList = document.getElementById('full-history-list');
        if (fullHistoryList) {
            fullHistoryList.innerHTML = html;
        }
    };

    if (logsFromCache && logsFromCache.length) {
        render(logsFromCache);
        return;
    }

    $.get(`${API_URL}/api/logs`, function(logs) {
        cachedLogs = logs;
        render(logs);
    });
}

// 清空库位中特定商品
function clearItemAtBin(binCode, itemCode) {
    const encodedBinCode = binCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    const encodedItemCode = itemCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    
    // 显示确认对话框
    $("#confirm-dialog h3 .lang-zh").text('确认清空此商品');
    $("#confirm-dialog h3 .lang-en").text('Confirm Clear Item');
    
    $(".confirm-details").html(`
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">库位：</span>
                <span class="lang-en">Bin:</span>
            </span>
            <span class="bin-code">${binCode}</span>
        </div>
        <div class="confirm-row">
            <span class="label">
                <span class="lang-zh">商品：</span>
                <span class="lang-en">Item:</span>
            </span>
            <span class="item-code">${itemCode}</span>
        </div>
    `);
    
    // 重置按钮显示和样式
    $("#confirm-yes").removeClass('success').addClass('warning');
    $("#confirm-yes .lang-zh").text('确认清空');
    $("#confirm-yes .lang-en").text('Clear Item');
    
    $("#confirm-middle").hide();
    
    $("#confirm-no").removeClass('cancel').addClass('cancel');
    $("#confirm-no .lang-zh").text('取消');
    $("#confirm-no .lang-en").text('Cancel');
    
    // 显示确认对话框
    $("#confirm-dialog").fadeIn(200);
    
    // 确认按钮事件
    $("#confirm-yes").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
        
        // 执行清空操作
        $.ajax({
            url: `${API_URL}/api/inventory/bin/${encodedBinCode}/item/${encodedItemCode}/clear`,
            type: 'DELETE',
            success: function(response) {
                // 清空成功后刷新显示
                setTimeout(searchBinContents, 100);
                setTimeout(updateHistoryDisplay, 100);
            },
            error: function(xhr, status, error) {
                alert(document.body.className.includes('lang-en')
                    ? "Failed to clear item, please try again"
                    : "清空商品失败，请重试");
            }
        });
    });
    
    // 取消按钮事件
    $("#confirm-no").on('click', function() {
        $("#confirm-yes").off('click');
        $("#confirm-middle").off('click');
        $("#confirm-no").off('click');
        $("#confirm-dialog").fadeOut(200);
    });
}

// 清除库位库存
function clearBinInventory(binCode) {
    // 移除之前可能存在的事件处理器
    $("#confirm-yes").off('click');
    $("#confirm-no").off('click');
    
    // 先获取库位中的商品信息
    const encodedBinCode = binCode.trim()
        .replace(/\//g, '___SLASH___')
        .replace(/\s/g, '___SPACE___');
    
    $.ajax({
        url: `${API_URL}/api/inventory/bin/${encodedBinCode}`,
        type: 'GET',
        success: function(contents) {
            // 修改确认对话框标题和内容
            $("#confirm-dialog h3 .lang-zh").text('确认清空库位');
            $("#confirm-dialog h3 .lang-en").text('Confirm Clear Bin');
            
            // 填充确认对话框
            $("#confirm-bin").text(binCode);
            
            // 创建商品详情HTML
            let detailsHtml = '';
            if (contents && contents.length > 0) {
                contents.forEach(inv => {
                    detailsHtml += `
                        <div class="confirm-item">
                            <div class="item-header">
                                <span class="lang-zh">
                                    商品 <span class="item-code">${inv.item_code}</span>: 
                                    <span class="quantity">${inv.total_pieces}</span> 件
                                </span>
                                <span class="lang-en">
                                    Item <span class="item-code">${inv.item_code}</span>: 
                                    <span class="quantity">${inv.total_pieces}</span> pcs
                                </span>
                            </div>
                            <div class="box-details">
                                ${inv.box_details.sort((a, b) => b.pieces_per_box - a.pieces_per_box)
                                    .map(detail => `
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
                    `;
                });
            } else {
                detailsHtml = `
                    <div class="empty-message">
                        <span class="lang-zh">该库位暂无库存</span>
                        <span class="lang-en">No inventory in this location</span>
                    </div>
                `;
            }
            
            // 更新确认对话框内容
            $(".confirm-details").html(`
                <div class="confirm-row">
                    <span class="label">
                        <span class="lang-zh">库位：</span>
                        <span class="lang-en">Bin:</span>
                    </span>
                    <span class="bin-code">${binCode}</span>
                </div>
                <div class="inventory-details">
                    ${detailsHtml}
                </div>
            `);
            
            // 设置按钮样式和文本 - 查询bin清空只需要两个按钮
            $("#confirm-yes").removeClass('warning').addClass('success');
            $("#confirm-yes .lang-zh").text('清空库位');
            $("#confirm-yes .lang-en").text('Clear Bin');
            $("#confirm-middle").hide();  // 隐藏中间按钮
            $("#confirm-no").removeClass('cancel').addClass('cancel');
            $("#confirm-no .lang-zh").text('取消');
            $("#confirm-no .lang-en").text('Cancel');
            
            // 显示确认对话框
            $("#confirm-dialog").fadeIn(200);
            
            // 确认按钮事件
            $("#confirm-yes").on('click', function() {
                // 立即移除事件处理器
                $("#confirm-yes").off('click');
                $("#confirm-no").off('click');
                $("#confirm-dialog").fadeOut(200);
                
                const encodedBinCode = binCode.trim()
                    .replace(/\//g, '___SLASH___')
                    .replace(/\s/g, '___SPACE___');
                
                $.ajax({
                    url: `${API_URL}/api/inventory/bin/${encodedBinCode}/clear`,
                    type: 'DELETE',
                    success: function(response) {
                        searchBinContents();  // 刷新查询结果
                        updateRecentHistory();  // 更新最近历史记录
                        updateFullHistory();    // 更新完整历史记录
                    },
                    error: function(xhr, status, error) {
                        console.error("Error clearing bin:", error);
                        searchBinContents();  // 刷新显示以反映当前状态
                        updateRecentHistory();  // 更新最近历史记录
                        updateFullHistory();    // 更新完整历史记录
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
        },
        error: function(xhr, status, error) {
            let errorMsg = document.body.className.includes('lang-en')
                ? "Failed to get bin contents!"
                : "获取库位内容失败！";
            if (xhr.responseJSON && xhr.responseJSON.error) {
                errorMsg = xhr.responseJSON.error;
            }
            alert(errorMsg);
        }
    });
}

 