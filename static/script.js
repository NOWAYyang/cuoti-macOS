let croppers = [];
let allFiles = [];

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

function destroyCroppers() {
  croppers.forEach((c) => c.destroy());
  croppers = [];
}

imageInput.addEventListener("change", () => {
  // 追加新选的文件，不清掉之前的
  for (const f of imageInput.files) allFiles.push(f);

  // 清掉所有 cropper 重新构建预览
  destroyCroppers();
  filePreview.innerHTML = "";

  for (let i = 0; i < allFiles.length; i++) {
    const card = document.createElement("div");
    card.className = "image-card";
    card.dataset.index = i;

    const header = document.createElement("div");
    header.className = "card-header";
    header.textContent = `第 ${i + 1} 题`;

    const cropDiv = document.createElement("div");
    cropDiv.className = "crop-container";
    const img = document.createElement("img");
    img.src = URL.createObjectURL(allFiles[i]);
    cropDiv.appendChild(img);

    const controls = document.createElement("div");
    controls.className = "error-controls";

    const tagsDiv = document.createElement("div");
    tagsDiv.className = "error-tags";
    tagsDiv.textContent = "错因标记（可多选）：";
    const tagLabels = ["计算错误", "概念不清", "审题失误", "粗心大意"];
    tagLabels.forEach((label) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag-btn";
      btn.dataset.tag = label;
      btn.textContent = label;
      tagsDiv.appendChild(btn);
    });
    controls.appendChild(tagsDiv);

    const note = document.createElement("textarea");
    note.className = "error-note";
    note.placeholder = "自定义备注（可选）";
    note.rows = 2;
    controls.appendChild(note);

    card.appendChild(header);
    card.appendChild(cropDiv);
    card.appendChild(controls);
    filePreview.appendChild(card);
  }

  requestAnimationFrame(() => {
    document.querySelectorAll(".crop-container img").forEach((img) => {
      const cropper = new Cropper(img, {
        viewMode: 1,
        autoCropArea: 0.85,
        background: false,
        responsive: true,
      });
      croppers.push(cropper);
    });
  });

  submitBtn.disabled = false;
});

filePreview.addEventListener("click", (e) => {
  const btn = e.target.closest(".tag-btn");
  if (btn) {
    btn.classList.toggle("selected");
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  error.classList.add("hidden");
  loading.classList.remove("hidden");
  submitBtn.disabled = true;

  const statusMessages = [
    { wait: 0, text: "正在 OCR 提取..." },
    { wait: 3000, text: "正在调用 AI 解题..." },
    { wait: 8000, text: "正在生成 Word 文档..." },
  ];

  statusMessages.forEach((msg) => {
    if (msg.wait === 0) {
      statusText.textContent = msg.text;
    } else {
      setTimeout(() => {
        statusText.textContent = msg.text;
      }, msg.wait);
    }
  });

  const formData = new FormData();
  formData.append("paper_size", document.getElementById("paper_size").value);
  formData.append("compress_quality", document.getElementById("compress_quality").value);
  formData.append("margin_mm", document.getElementById("margin_mm").value);
  formData.append("include_original_image", document.getElementById("include_original_image").checked ? "true" : "false");

  const errorTags = [];
  const errorNotes = [];

  for (let i = 0; i < croppers.length; i++) {
    let blob;
    try {
      const canvas = croppers[i].getCroppedCanvas({
        maxWidth: 4096,
        maxHeight: 4096,
      });
      blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.95));
    } catch {
      blob = allFiles[i];
    }
    formData.append("images", blob, `image_${i}.jpg`);

    const card = document.querySelector(`.image-card[data-index="${i}"]`);
    if (card) {
      const tags = [...card.querySelectorAll(".tag-btn.selected")].map((b) => b.dataset.tag);
      const note = card.querySelector(".error-note").value;
      errorTags.push(tags);
      errorNotes.push(note);
    } else {
      errorTags.push([]);
      errorNotes.push("");
    }
  }

  formData.append("error_data", JSON.stringify({ tags: errorTags, notes: errorNotes }));

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
    a.download = "错题本.docx";
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
