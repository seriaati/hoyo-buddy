// Render a Spine 4.0 or 4.1 animation loop to transparent PNG frames with spine-webgl in headless
// Chrome, picking the runtime by the skeleton's version.
// Usage: node render.mjs <skel> <atlas> <out_dir> [--anim <name>] [--fps 30] [--height 1500]
//     [--frames <count>] [--crop <left,top,width,height>] [--view <x,y,width,height>]
//     [--under <skel>,<atlas>[;<skel>,<atlas>...]] [--background <image>] [--untint-flags]
// --height is the pixel height of the skeleton's bounds over the whole loop.
// --frames renders only the first frames, e.g. 1 for a preview.
// --crop renders only that region of the bounds, in pixels from their top-left.
// --view uses a world rect (x, y its bottom-left, y up) as the bounds instead of the loop's.
// --under draws other skeletons beneath, bottom to top, playing the animation of the same name if
//     they have it.
// --background draws an image beneath everything, covering the bounds.
// --untint-flags renders slots keyed to pure channel colors (magenta, yellow, ...) untinted, miHoYo
//     uses them as flags for a custom shader.
// Set CHROME_PATH if Chrome isn't at /usr/bin/google-chrome.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import puppeteer from "puppeteer-core";

const require = createRequire(import.meta.url);
const [skelPath, atlasPath, outDir, ...rest] = process.argv.slice(2);
const opt = { fps: 30, height: 1500, anim: null, frames: null, crop: null, view: null, under: null, background: null };
for (let i = 0; i < rest.length; i++) {
  const key = rest[i].replace(/^--/, "");
  const value = rest[i + 1];
  if (value === undefined || value.startsWith("--")) {
    opt[key] = true;
  } else {
    opt[key] = value;
    i++;
  }
}
opt.fps = Number(opt.fps);
opt.height = Number(opt.height);
opt.frames = opt.frames === null ? null : Number(opt.frames);
opt.crop = opt.crop === null ? null : opt.crop.split(",").map(Number);
opt.view = opt.view === null ? null : opt.view.split(",").map(Number);

const dataUrl = (file) => {
  const ext = path.extname(file).slice(1).toLowerCase();
  const mime = ext === "jpg" ? "image/jpeg" : `image/${ext}`;
  return `data:${mime};base64,${fs.readFileSync(file).toString("base64")}`;
};

// Drawn bottom to top
const layerPaths = [...(opt.under ? opt.under.split(";").map((l) => l.split(",")) : []), [skelPath, atlasPath]];
const textures = {};
const layers = layerPaths.map(([skel, atlas]) => {
  const atlasText = fs.readFileSync(atlas, "utf8");
  for (const line of atlasText.split(/\r?\n/)) {
    const name = line.trim();
    if (/^[^:]+\.(png|webp|jpg)$/i.test(name)) textures[name] = dataUrl(path.join(path.dirname(atlas), name));
  }
  return { skel: fs.readFileSync(skel), atlasText };
});

// The binary starts with an 8 byte hash, then the version string prefixed by its length + 1
const skel = layers.at(-1).skel;
const version = skel.subarray(9, 8 + skel[8]).toString();
const runtime = version.startsWith("4.0.") ? "spine-webgl-4.0" : "@esotericsoftware/spine-webgl";

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"],
});
try {
  const page = await browser.newPage();
  await page.setContent("<canvas id=c></canvas>");
  await page.addScriptTag({ path: require.resolve(`${runtime}/dist/iife/spine-webgl.js`) });

  const info = await page.evaluate(
    async ({ layers, textures, background, fps, height, anim, crop, view, untintFlags }) => {
      const canvas = document.getElementById("c");
      const gl = canvas.getContext("webgl2", { alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true });
      const context = new spine.ManagedWebGLRenderingContext(gl);
      const loadImage = async (src) => {
        const img = new Image();
        img.src = src;
        await img.decode();
        return img;
      };

      const skeletons = [];
      for (const { skelB64, atlasText } of layers) {
        const atlas = new spine.TextureAtlas(atlasText);
        for (const p of atlas.pages) p.setTexture(new spine.GLTexture(context, await loadImage(textures[p.name])));
        const bytes = Uint8Array.from(atob(skelB64), (c) => c.charCodeAt(0));
        const data = new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);
        const skeleton = new spine.Skeleton(data);
        const state = new spine.AnimationState(new spine.AnimationStateData(data));
        skeletons.push({ atlas, data, skeleton, state });
      }

      // Without --anim: idle, then loop, then all, then the only animation, then one named *_idle
      const { data } = skeletons.at(-1);
      const byName = (name) => data.animations.find((a) => a.name.toLowerCase() === name);
      const animation = anim
        ? data.findAnimation(anim)
        : (byName("idle") ??
          byName("loop") ??
          byName("all") ??
          (data.animations.length === 1 ? data.animations[0] : null) ??
          data.animations.find((a) => a.name.toLowerCase().endsWith("_idle")));
      if (!animation) {
        throw new Error(`No animation to render, pass --anim; available: ${data.animations.map((a) => a.name)}`);
      }

      // The loop's length is its longest layer's
      const duration = Math.max(...skeletons.map(({ data }) => data.findAnimation(animation.name)?.duration ?? 0));
      const frameCount = Math.max(1, Math.round(duration * fps));
      const pose = (frame) => {
        for (const { data, skeleton, state } of skeletons) {
          skeleton.setToSetupPose();
          state.clearTracks();
          if (data.findAnimation(animation.name)) {
            state.setAnimation(0, animation.name, true);
            state.update(frame / fps);
            state.apply(skeleton);
          }
          if (untintFlags) {
            for (const { color } of skeleton.slots) {
              const rgb = [color.r, color.g, color.b];
              if (rgb.every((v) => v === 0 || v === 1) && rgb.includes(1)) color.set(1, 1, 1, color.a);
            }
          }
          skeleton.updateWorldTransform();
        }
      };

      // Union of the bounds over the whole loop so no frame gets clipped
      let [minX, minY, maxX, maxY] = view
        ? [view[0], view[1], view[0] + view[2], view[1] + view[3]]
        : [Infinity, Infinity, -Infinity, -Infinity];
      const offset = new spine.Vector2(), size = new spine.Vector2();
      for (let f = 0; f < (view ? 0 : frameCount); f++) {
        pose(f);
        for (const { skeleton } of skeletons) {
          skeleton.getBounds(offset, size, []);
          minX = Math.min(minX, offset.x);
          minY = Math.min(minY, offset.y);
          maxX = Math.max(maxX, offset.x + size.x);
          maxY = Math.max(maxY, offset.y + size.y);
        }
      }
      const scale = height / (maxY - minY);
      const fullWidth = Math.ceil((maxX - minX) * scale);
      const fullHeight = Math.ceil((maxY - minY) * scale);
      const [left, top, width, cropHeight] = crop ?? [0, 0, fullWidth, fullHeight];
      canvas.width = width;
      canvas.height = cropHeight;

      // The canvas's top is the bounds' maxY since skeleton y points up
      const renderer = new spine.SceneRenderer(canvas, context, true);
      renderer.camera.position.x = minX + (left + width / 2) / scale;
      renderer.camera.position.y = maxY - (top + cropHeight / 2) / scale;
      renderer.camera.viewportWidth = width / scale;
      renderer.camera.viewportHeight = cropHeight / scale;
      gl.viewport(0, 0, canvas.width, canvas.height);

      // The background covers the bounds, centered
      const output = document.createElement("canvas");
      output.width = width;
      output.height = cropHeight;
      const output2d = output.getContext("2d");
      const backgroundImage = background ? await loadImage(background) : null;
      const drawBackground = () => {
        const bgScale = Math.max(fullWidth / backgroundImage.width, fullHeight / backgroundImage.height);
        const bgWidth = backgroundImage.width * bgScale, bgHeight = backgroundImage.height * bgScale;
        output2d.drawImage(
          backgroundImage, (fullWidth - bgWidth) / 2 - left, (fullHeight - bgHeight) / 2 - top, bgWidth, bgHeight,
        );
      };

      window.renderFrame = (f) => {
        pose(f);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        renderer.begin();
        for (const { atlas, skeleton } of skeletons) {
          renderer.drawSkeleton(skeleton, atlas.pages.some((p) => p.pma));
        }
        renderer.end();
        if (!backgroundImage) return canvas.toDataURL("image/png").split(",")[1];

        output2d.clearRect(0, 0, width, cropHeight);
        drawBackground();
        output2d.drawImage(canvas, 0, 0);
        return output.toDataURL("image/png").split(",")[1];
      };
      return { animation: animation.name, frameCount, width: fullWidth, height: fullHeight };
    },
    {
      ...opt,
      layers: layers.map(({ skel, atlasText }) => ({ skelB64: skel.toString("base64"), atlasText })),
      textures,
      background: opt.background ? dataUrl(opt.background) : null,
      untintFlags: opt["untint-flags"] === true,
    },
  );

  fs.mkdirSync(outDir, { recursive: true });
  for (let f = 0; f < Math.min(info.frameCount, opt.frames ?? Infinity); f++) {
    const b64 = await page.evaluate((f) => window.renderFrame(f), f);
    fs.writeFileSync(path.join(outDir, `${String(f).padStart(4, "0")}.png`), Buffer.from(b64, "base64"));
  }
  console.log(JSON.stringify(info));
} finally {
  await browser.close();
}
