/* 通用前端工具：Toast 提示、确认框、输入框，替代原生 alert/confirm/prompt */

(function () {
  // ---- Toast 轻提示 ----
  function showToast(msg, type) {
    type = type || 'info'; // info / success / error
    var el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.textContent = msg;
    document.body.appendChild(el);
    // 触发动画
    requestAnimationFrame(function () { el.classList.add('show'); });
    setTimeout(function () {
      el.classList.remove('show');
      setTimeout(function () { el.remove(); }, 300);
    }, 2200);
  }

  // ---- 确认框 ----
  function showConfirm(msg, onOk, onCancel) {
    var box = _buildModal({
      title: '提示',
      body: '<p class="modal-msg">' + _escapeHtml(msg) + '</p>',
      buttons: [
        { text: '取消', cls: 'btn-secondary', action: function () { close(); if (onCancel) onCancel(); } },
        { text: '确定', cls: 'btn-primary', action: function () { close(); if (onOk) onOk(); } }
      ]
    });
    function close() { box.remove(); }
  }

  // ---- 输入框 ----
  function showPrompt(msg, defaultValue, onOk, onCancel) {
    var box = _buildModal({
      title: '请输入',
      body: '<p class="modal-msg">' + _escapeHtml(msg) + '</p>' +
            '<input type="text" class="modal-input" id="_promptInput" value="' +
            _escapeHtml(defaultValue || '') + '">',
      buttons: [
        { text: '取消', cls: 'btn-secondary', action: function () { close(); if (onCancel) onCancel(); } },
        { text: '确定', cls: 'btn-primary', action: function () {
            var v = document.getElementById('_promptInput').value;
            close();
            if (onOk) onOk(v);
          } }
      ]
    });
    function close() { box.remove(); }
    setTimeout(function () {
      var inp = document.getElementById('_promptInput');
      if (inp) { inp.focus(); inp.select(); }
    }, 50);
  }

  // ---- 内部：构建模态框 ----
  function _buildModal(opts) {
    var mask = document.createElement('div');
    mask.className = 'modal-mask';
    var dialog = document.createElement('div');
    dialog.className = 'modal-dialog';
    var html = '<div class="modal-header"><span>' + (opts.title || '提示') + '</span>' +
               '<span class="modal-close">&times;</span></div>' +
               '<div class="modal-body">' + (opts.body || '') + '</div>' +
               '<div class="modal-footer">';
    (opts.buttons || []).forEach(function (b) {
      html += '<button class="btn ' + (b.cls || '') + '">' + b.text + '</button>';
    });
    html += '</div>';
    dialog.innerHTML = html;
    mask.appendChild(dialog);
    document.body.appendChild(mask);
    // 绑定按钮
    var btns = dialog.querySelectorAll('.modal-footer .btn');
    (opts.buttons || []).forEach(function (b, i) {
      btns[i].addEventListener('click', b.action);
    });
    dialog.querySelector('.modal-close').addEventListener('click', function () { mask.remove(); });
    mask.addEventListener('click', function (e) {
      if (e.target === mask) mask.remove();
    });
    return mask;
  }

  function _escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
  }

  // 暴露到全局
  window.showToast = showToast;
  window.showConfirm = showConfirm;
  window.showPrompt = showPrompt;
})();
