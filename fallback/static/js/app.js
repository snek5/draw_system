// Small bits of behaviour htmx doesn't cover.

// Keep the "RNG Seed:" line in step with the seed box, as before.
document.addEventListener("input", (event) => {
  if (event.target.id !== "seed") return;
  const echo = document.getElementById("seed-echo");
  if (echo) echo.textContent = event.target.value;
});

// On the draw screen, Spacebar downloads the winners revealed so far.
document.addEventListener("keydown", (event) => {
  if (event.key !== " " || !document.getElementById("draw-screen")) return;
  event.preventDefault();
  window.location.href = "/draw/download";
});

// htmx ignores error responses by default; surface them instead of failing silently.
document.addEventListener("htmx:responseError", (event) => {
  const xhr = event.detail.xhr;
  window.alert(xhr.responseText || `Request failed (${xhr.status}).`);
});
