/* Pick a random tagline on page load. */
document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("tagline");
  if (!el) return;
  var lines = el.querySelectorAll(".tagline-option");
  if (lines.length === 0) return;
  var pick = Math.floor(Math.random() * lines.length);
  for (var i = 0; i < lines.length; i++) {
    lines[i].style.display = i === pick ? "inline" : "none";
  }
});
