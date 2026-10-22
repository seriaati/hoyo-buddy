// Render a Spine 4.1 animation loop to transparent PNG frames with spine-webgl in headless Chrome.
// Usage: node render.mjs <skel> <atlas> <out_dir> [--anim <name>] [--fps 30] [--height 1500]
//     [--frames <count>] [--crop <left,top,width,height>]
// --height is the pixel height of the skeleton's bounds over the whole loop.
// --frames renders only the first frames, e.g. 1 for a preview.
// --crop renders only that region of the bounds, in pixels from their top-left.
// Set CHROME_PATH if Chrome isn't at /usr/bin/google-chrome.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import puppeteer from "puppeteer-core";

const require = createRequire(import.meta.url);
const [skelPath, atlasPath, outDir, ...rest] = process.argv.slice(2);
const opt = { fps: 30, height: 1500, anim: null, frames: null, crop: null };
for (let i = 0; i < rest.length; i += 2) opt[rest[i].replace(/^--/, "")] = rest[i + 1];
opt.fps = Number(opt.fps);
opt.height = Number(opt.height);
opt.frames = opt.frames === null ? null : Number(opt.frames);
opt.crop = opt.crop === null ? null : opt.crop.split(",").map(Number);

const atlasText = fs.readFileSync(atlasPath, "utf8");
const pageNames = atlasText.split(/\r?\n/).filter((l) => /^[^:]+\.(png|webp|jpg)$/i.test(l.trim()));
const textures = Object.fromEntries(
  pageNames.map((n) => {
    const name = n.trim();
    const ext = path.extname(name).slice(1).toLowerCase();
    const mime = ext === "jpg" ? "image/jpeg" : `image/${ext}`;
    const data = fs.readFileSync(path.join(path.dirname(atlasPath), name)).toString("base64");
    return [name, `data:${mime};base64,${data}`];
  }),
);

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"],
});
try {
  const page = await browser.newPage();
  await page.setContent("<canvas id=c></canvas>");
  await page.addScriptTag({ path: require.resolve("@esotericsoftware/spine-webgl/dist/iife/spine-webgl.js") });

  const info = await page.evaluate(
    async ({ skelB64, atlasText, textures, fps, height, anim, crop }) => {
      const canvas = document.getElementById("c");
      const gl = canvas.getContext("webgl2", { alpha: true, premultipliedAlpha: true, preserveDrawingBuffer: true });
      const context = new spine.ManagedWebGLRenderingContext(gl);

      const atlas = new spine.TextureAtlas(atlasText);
      for (const p of atlas.pages) {
        const img = new Image();
        img.src = textures[p.name];
        await img.decode();
        p.setTexture(new spine.GLTexture(context, img));
      }
      const bytes = Uint8Array.from(atob(skelB64), (c) => c.charCodeAt(0));
      const data = new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);
      // Without --anim: idle, then loop, then all, then the only animation
      const byName = (name) => data.animations.find((a) => a.name.toLowerCase() === name);
      const animation = anim
        ? data.findAnimation(anim)
        : (byName("idle") ?? byName("loop") ?? byName("all") ?? (data.animations.length === 1 ? data.animations[0] : null));
      if (!animation) {
        throw new Error(`No animation to render, pass --anim; available: ${data.animations.map((a) => a.name)}`);
      }

      const skeleton = new spine.Skeleton(data);
      const state = new spine.AnimationState(new spine.AnimationStateData(data));
      const frameCount = Math.max(1, Math.round(animation.duration * fps));
      const pose = (frame) => {
        skeleton.setToSetupPose();
        state.clearTracks();
        state.setAnimation(0, animation.name, true);
        state.update(frame / fps);
        state.apply(skeleton);
        skeleton.updateWorldTransform();
      };

      // Union of the bounds over the whole loop so no frame gets clipped
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      const offset = new spine.Vector2(), size = new spine.Vector2();
      for (let f = 0; f < frameCount; f++) {
        pose(f);
        skeleton.getBounds(offset, size, []);
        minX = Math.min(minX, offset.x);
        minY = Math.min(minY, offset.y);
        maxX = Math.max(maxX, offset.x + size.x);
        maxY = Math.max(maxY, offset.y + size.y);
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

      window.renderFrame = (f) => {
        pose(f);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        renderer.begin();
        renderer.drawSkeleton(skeleton, atlas.pages.some((p) => p.pma));
        renderer.end();
        return canvas.toDataURL("image/png").split(",")[1];
      };
      return { animation: animation.name, frameCount, width: fullWidth, height: fullHeight };
    },
    { skelB64: fs.readFileSync(skelPath).toString("base64"), atlasText, textures, ...opt },
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
