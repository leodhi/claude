// ==UserScript==
// @name         Inoreader Auto Refresh
// @namespace    https://github.com/leodhi/claude
// @version      1.0
// @description  Automatically refreshes the Inoreader feed every 30 seconds so you don't have to pull down to refresh.
// @author       you
// @match        https://www.inoreader.com/*
// @match        https://*.inoreader.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=inoreader.com
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const REFRESH_INTERVAL_MS = 30000;

  // Selectors Inoreader has used for its manual refresh control, tried in order.
  const REFRESH_BUTTON_SELECTORS = [
    '[data-target="refresh"]',
    '.refresh_button',
    'div.refresh',
    'a[title="Refresh"]',
    'button[title="Refresh"]',
    '[aria-label="Refresh"]',
  ];

  function clickRefreshButton() {
    for (const selector of REFRESH_BUTTON_SELECTORS) {
      const el = document.querySelector(selector);
      if (el) {
        el.click();
        return true;
      }
    }
    return false;
  }

  function simulateRefreshShortcut() {
    // Inoreader's default keyboard shortcut for "refresh" is "r".
    const target = document.activeElement || document.body;
    for (const type of ['keydown', 'keypress', 'keyup']) {
      target.dispatchEvent(
        new KeyboardEvent(type, {
          key: 'r',
          code: 'KeyR',
          keyCode: 82,
          which: 82,
          bubbles: true,
          cancelable: true,
        })
      );
    }
  }

  function refresh() {
    if (!clickRefreshButton()) {
      simulateRefreshShortcut();
    }
  }

  setInterval(refresh, REFRESH_INTERVAL_MS);
})();
