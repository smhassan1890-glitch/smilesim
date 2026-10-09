/**
 * Payment recipient <select> filtered by the chosen payment method.
 *
 * Markup contract:
 *   <select id="id_payment_method">…</select>
 *   <select data-recipient-for="id_payment_method">
 *     <option value="">…</option>
 *     <option value="7" data-method="3">Jawwal Pay — …</option>
 *   </select>
 *
 * Recipient options whose `data-method` differs from the selected method
 * are hidden and disabled; if the current choice becomes hidden the
 * recipient select is reset to the empty option. Runs on load and on
 * every method change.
 */
(function () {
  "use strict";

  function bind(recipientSelect) {
    var methodSelect = document.getElementById(
      recipientSelect.getAttribute("data-recipient-for")
    );
    if (!methodSelect) return;

    function apply() {
      var method = methodSelect.value;
      var options = recipientSelect.querySelectorAll("option[data-method]");
      for (var i = 0; i < options.length; i++) {
        var hide = options[i].getAttribute("data-method") !== method;
        options[i].hidden = hide;
        options[i].disabled = hide;
        if (hide && options[i].selected) recipientSelect.value = "";
      }
    }

    methodSelect.addEventListener("change", apply);
    apply();
  }

  function init() {
    var selects = document.querySelectorAll("select[data-recipient-for]");
    for (var i = 0; i < selects.length; i++) bind(selects[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
