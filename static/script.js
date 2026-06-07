const form = document.getElementById("upload-form");
const imageInput = document.getElementById("image-input");
const filePreview = document.getElementById("file-preview");
const submitBtn = document.getElementById("submit-btn");
const loading = document.getElementById("loading");
const statusText = document.getElementById("status-text");
const error = document.getElementById("error");
const errorText = document.getElementById("error-text");
const qualitySlider = document.getElementById("compress_quality");
const qualityValue = document.getElementById("quality-value");

qualitySlider.addEventListener("input", () => {
  qualityValue.textContent = qualitySlider.value;
});

imageInput.addEventListener("change", () => {
  const files = imageInput.files;
  filePreview.innerHTML = "";
  if (files.length === 0) {
    submitBtn.disabled = true;
    return;
  }
  const count = files.length > 5 ? 5 : files.length;
  for (let i = 0; i < count; i++) {
    const img = document.createElement("img");
    img.className = "thumb";
    img.src = URL.createObjectURL(files[i]);
    filePreview.appendChild(img);
  }
  const countLabel = document.createElement("div");
  countLabel.className = "count";
  countLabel.textContent = `已选择 ${files.length} 张图片`;
  filePreview.appendChild(countLabel);
  submitBtn.disabled = false;
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  error.classList.add("hidden");
  loading.classList.remove("hidden");
  submitBtn.disabled = true;

  const statusMessages = [
    { wait: 0, text: "正在 OCR 提取..." },
    { wait: 3000, text: "正在调用 AI 解题..." },
    { wait: 8000, text: "正在生成 PDF..." },
  ];

  let statusTimer = 0;
  statusMessages.forEach((msg) => {
    if (msg.wait === 0) {
      statusText.textContent = msg.text;
    } else {
      setTimeout(() => {
        statusText.textContent = msg.text;
      }, msg.wait);
    }
  });

  const formData = new FormData(form);
  const files = imageInput.files;
  for (let i = 0; i < files.length; i++) {
    formData.append("images", files[i]);
  }

  try {
    const res = await fetch("/upload", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({ error: `服务器错误 (${res.status})` }));
      throw new Error(data.error || `请求失败 (${res.status})`);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "错题本.pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    errorText.textContent = err.message;
    error.classList.remove("hidden");
  } finally {
    loading.classList.add("hidden");
    submitBtn.disabled = false;
  }
});
