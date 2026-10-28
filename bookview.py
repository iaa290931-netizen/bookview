#!/usr/bin/env python3
"""BookView - candlestick chart x order-book heatmap (simulated data).

Setup:  pip install pygame numpy
Run:    python bookview.py
Keys:   Space pause | 1/2/3 speed | H heatmap | C candles | T trades
        Up/Down sensitivity | F11 fullscreen | Esc quit
"""
import math
import os
import random
import sys

try:
    import numpy as np
    import pygame
except ImportError as e:
    print("Missing package:", e)
    print("Run:  python -m pip install pygame numpy")
    input("Press Enter to close...")
    sys.exit(1)

L, P0, CPC, MAXC = 400, 4800, 12, 1500   # levels, base price, ticks/candle, history length
BG, PANEL, FG, MUTE, LINE = (11, 15, 23), (18, 24, 38), (214, 222, 235), (122, 134, 154), (31, 41, 55)
UP, DN = (38, 166, 154), (239, 83, 80)

# colour map: background -> blue -> cyan -> yellow -> red
_stops = np.array([BG, (25, 55, 150), (0, 170, 200), (240, 220, 60), (255, 70, 40)], float)
_x = np.linspace(0, len(_stops) - 1, 256)
LUT = np.stack([np.interp(_x, range(len(_stops)), _stops[:, c]) for c in range(3)], 1).astype(np.uint8)


class Sim:
    def __init__(self):
        r = np.random.random(L)
        self.walls = np.where(r < .08, 3 + np.random.random(L) * 6, .3 + np.random.random(L) * .7).astype(np.float32)
        self.book = np.zeros(L, np.float32)
        self.hist = np.zeros((MAXC, L), np.float32)
        self.mids = np.zeros(MAXC)
        self.n = 0
        self.base = 0
        self.t = 0
        self.mid, self.vel, self.cen = 5000.5, 0.0, 5000.0
        self.trades = []  # (abs_col, price, size, is_buy)
        for _ in range(350):
            self.step()
        self.open = self.mids[0]

    def step(self):
        self.vel = self.vel * .9 + (random.random() - .5) * .35 + (5000 - self.mid) * .002
        self.mid += self.vel
        bb = math.floor(self.mid)
        if random.random() < .15:
            i = random.randrange(L)
            self.walls[i] = 4 + random.random() * 7 if random.random() < .2 else .2 + random.random() * .8
        d = np.abs(np.arange(L) + P0 + .5 - self.mid)
        tg = self.walls * 120 * np.exp(-d / 70)
        self.book += (tg - self.book) * .12 + (np.random.random(L) - .5) * 4
        np.maximum(self.book, 0, out=self.book)
        if random.random() < .5:
            buy = random.random() < (.7 if self.vel > 0 else .3)
            size = 30 + random.random() * 60 if random.random() < .1 else 2 + random.random() * 10
            p = bb + 1 if buy else bb
            self.trades.append((self.t, p, size, buy))
            self.book[p - P0] = max(0, self.book[p - P0] - size * 2)
        if self.n == MAXC:
            self.hist[:-1] = self.hist[1:]
            self.mids[:-1] = self.mids[1:]
            self.base += 1
        else:
            self.n += 1
        self.hist[self.n - 1] = self.book
        self.mids[self.n - 1] = self.mid
        self.t += 1
        while self.trades and self.trades[0][0] < self.base:
            self.trades.pop(0)
        self.cen += (self.mid - self.cen) * .1


class App:
    def __init__(self, size=(1280, 720)):
        pygame.init()
        pygame.display.set_caption("BookView")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.font = pygame.font.SysFont("menlo,consolas,dejavusansmono,monospace", 13)
        self.big = pygame.font.SysFont("menlo,consolas,dejavusansmono,monospace", 18, bold=True)
        self.cache = {}
        self.sim = Sim()
        self.running, self.speed, self.gain = True, 1, 1.0
        self.heat = self.candle = self.trade = True

    def text(self, s, color, big=False):
        key = (s, color, big)
        if key not in self.cache:
            if len(self.cache) > 600:
                self.cache.clear()
            self.cache[key] = (self.big if big else self.font).render(s, True, color)
        return self.cache[key]

    def draw(self):
        sc, s = self.screen, self.sim
        W, H = sc.get_size()
        sc.fill(BG)
        top, RW = 40, 132
        cw, ch = W - RW, H - top
        R = 72
        rowH = ch / R
        hi = round(s.cen + R / 2)
        colw = max(2, min(5, cw // 160))
        N = s.n
        n = min(N, cw // colw)
        k0 = N - n
        Y = lambda p: top + (hi + 1 - p) * rowH
        X = lambda k: cw - (N - k) * colw

        # header
        pygame.draw.rect(sc, PANEL, (0, 0, W, top))
        d = s.mid - s.open
        sc.blit(self.text("SIM-FUT", FG, True), (12, 10))
        sc.blit(self.text(f"{s.mid:.2f}", FG, True), (110, 10))
        sc.blit(self.text(f"{d:+.2f}", UP if d >= 0 else DN, True), (200, 10))
        state = "PAUSED" if not self.running else f"{self.speed}x"
        help_ = f"{state} | Space pause  1/2/3 speed  H heat[{'x' if self.heat else ' '}]  C candle[{'x' if self.candle else ' '}]  T trade[{'x' if self.trade else ' '}]  Up/Down gain {self.gain:.1f}"
        sc.blit(self.text(help_, MUTE), (300, 13))

        # grid
        for r in range(0, R, 6):
            y = int(top + r * rowH)
            pygame.draw.line(sc, LINE, (0, y), (cw, y))

        # heatmap (numpy -> surface)
        i_hi = hi - P0
        i_lo = i_hi - R + 1
        if self.heat and n > 0 and i_lo >= 0 and i_hi < L:
            block = s.hist[k0:N, i_lo:i_hi + 1][:, ::-1]
            v = np.clip(block / (300 / self.gain), 0, 1)
            v = np.where(v < .05, 0, v ** .7)
            img = LUT[(v * 255).astype(np.uint8)]
            surf = pygame.transform.scale(pygame.surfarray.make_surface(img), (n * colw, int(ch)))
            sc.blit(surf, (cw - n * colw, top))

        # candles
        if self.candle:
            groups, cur, gi = [], None, -1
            for k in range(k0, N):
                q = (s.base + k) // CPC
                m = s.mids[k]
                if q != gi:
                    gi = q
                    cur = [m, m, m, m, k, k]  # o h l c first last
                    groups.append(cur)
                else:
                    cur[1] = max(cur[1], m); cur[2] = min(cur[2], m); cur[3] = m; cur[5] = k
            for o, h, l, c, a, z in groups:
                x0, x1 = X(a), X(z) + colw
                xm = (x0 + x1) / 2
                col = UP if c >= o else DN
                pygame.draw.line(sc, col, (xm, Y(h)), (xm, Y(l)))
                y1, y2 = Y(o), Y(c)
                pygame.draw.rect(sc, col, (x0 + 1, min(y1, y2), max(1, x1 - x0 - 2), max(1.5, abs(y1 - y2))))

        # trades
        if self.trade:
            ov = pygame.Surface((cw, H), pygame.SRCALPHA)
            for c, p, size, buy in s.trades:
                k = c - s.base
                if k < k0 or k >= N:
                    continue
                rad = max(2, int(math.sqrt(size) * 1.4))
                pygame.draw.circle(ov, (*(UP if buy else DN), 140), (int(X(k) + colw / 2), int(Y(p + .5))), rad)
            sc.blit(ov, (0, 0))

        # last price line
        ly = Y(s.mid)
        for x in range(0, cw, 8):
            pygame.draw.line(sc, MUTE, (x, ly), (x + 4, ly))

        # DOM ladder
        pygame.draw.rect(sc, PANEL, (cw, top, RW, ch))
        pygame.draw.line(sc, LINE, (cw, top), (cw, H))
        last, bb = s.hist[N - 1], math.floor(s.mid)
        step = 1 if rowH >= 11 else 2 if rowH >= 6 else 5
        for r in range(R):
            p = hi - r
            i = p - P0
            if not 0 <= i < L:
                continue
            y = top + r * rowH
            w = min(1, last[i] / 400) * 74
            if w >= 1:
                bar = pygame.Surface((int(w), max(1, int(rowH) - 1)), pygame.SRCALPHA)
                bar.fill((*(UP if p <= bb else DN), 140))
                sc.blit(bar, (cw + 52, y))
            if p % step == 0:
                sc.blit(self.text(str(p), FG if p in (bb, bb + 1) else MUTE), (cw + 6, y + rowH / 2 - 7))
        pygame.draw.rect(sc, FG, (cw, ly - 8, RW, 16))
        sc.blit(self.text(f"{s.mid:.2f}", BG), (cw + 6, ly - 7))

        # crosshair
        mx, my = pygame.mouse.get_pos()
        if pygame.mouse.get_focused() and 0 <= mx < cw and my > top:
            pygame.draw.line(sc, MUTE, (mx, top), (mx, H))
            pygame.draw.line(sc, MUTE, (0, my), (cw, my))
            p = hi - int((my - top) // rowH)
            k = N - math.ceil((cw - mx) / colw)
            i = p - P0
            if 0 <= k < N and 0 <= i < L:
                t = self.text(f"price {p}   depth {s.hist[k, i]:.0f}", FG)
                bx = min(mx + 10, cw - t.get_width() - 12)
                pygame.draw.rect(sc, PANEL, (bx, my - 26, t.get_width() + 12, 20))
                sc.blit(t, (bx + 6, my - 24))

    def run(self, frames=None):
        clock, acc, n = pygame.time.Clock(), 0.0, 0
        while True:
            dt = clock.tick(30) / 1000
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN:
                    k = e.key
                    if k == pygame.K_ESCAPE:
                        return
                    elif k == pygame.K_SPACE:
                        self.running = not self.running
                    elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
                        self.speed = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 4}[k]
                    elif k == pygame.K_h:
                        self.heat = not self.heat
                    elif k == pygame.K_c:
                        self.candle = not self.candle
                    elif k == pygame.K_t:
                        self.trade = not self.trade
                    elif k == pygame.K_UP:
                        self.gain = min(2.0, self.gain + .1)
                    elif k == pygame.K_DOWN:
                        self.gain = max(.3, self.gain - .1)
                    elif k == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
            if self.running:
                acc += dt * self.speed
                while acc >= .12:
                    self.sim.step()
                    acc -= .12
            self.draw()
            pygame.display.flip()
            n += 1
            if frames and n >= frames:
                return


if __name__ == "__main__":
    if "--selftest" in sys.argv:  # headless check: render a frame to PNG
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        app = App()
        for _ in range(100):
            app.sim.step()
        app.draw()
        pygame.image.save(app.screen, "selftest.png")
        print("ok")
    else:
        try:
            App().run()
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                with open("bookview_error.txt", "w") as f:
                    traceback.print_exc(file=f)
                input("Error occurred. Press Enter to close...")
            except Exception:
                pass
