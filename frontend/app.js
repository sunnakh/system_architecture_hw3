function newRequestId() {
  if (window.crypto && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  // RFC4122 v4 fallback for non-secure contexts
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
    /[xy]/g,
    (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    }
  );
}

const form = document.getElementById("uploadForm");
const result = document.getElementById("result");
const err = document.getElementById("error");

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  err.hidden = true;

  const file = document.getElementById("file").files[0];

  if (!file) return;

  if (file.size > 10 * 1024 * 1024) {
    err.textContent = "File is larger than 10 MB.";
    err.hidden = false;
    return;
  }

  const fd = new FormData();
  fd.append("file", file);

  const rid = newRequestId();

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      headers: {
        "X-Request-ID": rid
      },
      body: fd
    });

    if (!res.ok) {
      const detail = await res.text();
      throw new Error(res.status + " " + detail);
    }

    const data = await res.json();

    document.getElementById("shortLink").href =
      data.short_url;

    document.getElementById("shortLink").textContent =
      data.short_url;

    document.getElementById("preview").src =
      data.thumb_url;

    result.hidden = false;

  } catch (e) {
    err.textContent = "Upload failed: " + e.message;
    err.hidden = false;
  }
});