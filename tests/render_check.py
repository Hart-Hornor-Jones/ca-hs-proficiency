#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render check for index.html, driven by Playwright (Chromium, headless).

    pip install playwright && playwright install chromium
    python tests/render_check.py                       # opens ../index.html
    python tests/render_check.py --html path/to/index.html
    python tests/render_check.py --executable-path /path/to/chrome   # use an existing Chromium

The script opens the page from a file:// URL, exercises every <select> (each
option at least once), every <button> and role="button" link, every checkbox,
radio and range input, and the canvas interactions (hover, wheel zoom, click to
tag a school, double-click to clear), including the derived residual plots the
page can spawn. It fails on any console message of type "error", any uncaught
page error, any failed network request, or any response with status 400 or
higher, and on a few sanity assertions (the plot has dots, the year label is
filled, the derived plots appear and disappear). Exit status 1 on failure.
"""
import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SETTLE_MS = 40          # pause after each control change so the page's handlers run
ANIM_TIMEOUT_MS = 20000  # longest we wait for a spawned plot's animation


class Recorder:
    """Collects everything that should fail the run."""

    def __init__(self):
        self.problems = []
        self.exercised = {"select_options": 0, "buttons": 0, "checks": 0, "ranges": 0, "canvas": 0}

    def on_console(self, msg):
        if msg.type == "error":
            self.problems.append("console error: " + msg.text)

    def on_pageerror(self, err):
        self.problems.append("page error: " + str(err))

    def on_requestfailed(self, req):
        self.problems.append("request failed: %s (%s)" % (req.url, req.failure))

    def on_response(self, resp):
        if resp.status >= 400:
            self.problems.append("response %d: %s" % (resp.status, resp.url))

    def fail(self, text):
        self.problems.append(text)


def wait_idle(page, timeout_ms=ANIM_TIMEOUT_MS):
    """Wait until every plot's animation queue is empty."""
    page.wait_for_function(
        "() => typeof chain !== 'undefined' && chain.every(c => c.plot.getMotion().queueLen === 0)",
        timeout=timeout_ms)


def settle(page):
    page.wait_for_timeout(SETTLE_MS)


def set_range(page, selector, value):
    page.evaluate(
        "([sel, v]) => { const el = document.querySelector(sel); el.value = v; "
        "el.dispatchEvent(new Event('input', {bubbles: true})); "
        "el.dispatchEvent(new Event('change', {bubbles: true})); }",
        [selector, str(value)])


def exercise_select(page, rec, selector, restore=None):
    """Select every option of a <select> once; return the list of option values."""
    values = page.eval_on_selector(selector, "el => Array.from(el.options).map(o => o.value)")
    for v in values:
        page.select_option(selector, v)
        settle(page)
        rec.exercised["select_options"] += 1
    if restore is not None and restore in values:
        page.select_option(selector, restore)
        settle(page)
    return values


def exercise_ranges(page, rec):
    for sel in ["#year", "#s-spin", "#s-tilt", "#s-shear"]:
        info = page.eval_on_selector(sel, "el => ({min: +el.min, max: +el.max, value: el.value, disabled: el.disabled})")
        if info["disabled"]:
            continue
        for v in (info["min"], (info["min"] + info["max"]) / 2, info["max"], info["value"]):
            set_range(page, sel, v)
            settle(page)
        rec.exercised["ranges"] += 1


def canvas_interactions(page, rec, canvas):
    box = canvas.bounding_box()
    if not box or box["width"] < 50 or box["height"] < 50:
        rec.fail("canvas has no size: %s" % box)
        return
    cx, cy = box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.45
    page.mouse.move(cx, cy)
    settle(page)
    for dx in range(0, 120, 12):          # sweep across the plot so the tooltip finds dots
        page.mouse.move(cx - 60 + dx, cy)
    page.mouse.wheel(0, -300)             # zoom in
    settle(page)
    page.mouse.wheel(0, 300)              # zoom out
    settle(page)
    page.mouse.click(cx, cy)              # tag a school
    settle(page)
    page.mouse.dblclick(cx, cy)           # clear tags
    settle(page)
    page.mouse.move(box["x"] - 5, box["y"] - 5)   # mouseleave
    settle(page)
    rec.exercised["canvas"] += 1


def exercise_plot_buttons(page, rec, k):
    """Click the five view buttons of plot k (rj spawns or removes the next plot)."""
    for v in ("x", "y", "r", "joint"):
        page.click("#psec-%d .stack button[data-v=%s]" % (k, v))
        settle(page)
        rec.exercised["buttons"] += 1
    wait_idle(page)


def run(html_path, executable_path, headless=True):
    rec = Recorder()
    with sync_playwright() as p:
        kwargs = {"headless": headless, "args": ["--no-sandbox"]}
        if executable_path:
            kwargs["executable_path"] = executable_path
        browser = p.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("console", rec.on_console)
        page.on("pageerror", rec.on_pageerror)
        page.on("requestfailed", rec.on_requestfailed)
        page.on("response", rec.on_response)

        page.goto(Path(html_path).resolve().as_uri(), wait_until="load")
        page.wait_for_selector("#psec-1 canvas")
        wait_idle(page)

        # ---- sanity on the default view
        n = page.evaluate("() => chain[0].plot.getN()")
        if not n or n < 100:
            rec.fail("default plot shows %s dots (expected hundreds)" % n)
        if not page.text_content("#yearval").strip():
            rec.fail("year label is empty")
        if page.locator("#xsel option").count() < 10:
            rec.fail("x-axis menu has too few options")

        # ---- toggles that reveal controls
        page.click("#guidetog"); settle(page); rec.exercised["buttons"] += 1
        page.click("#psec-1 .pctl"); settle(page); rec.exercised["buttons"] += 1   # show chart controls
        page.click("#motiontoggle"); settle(page); rec.exercised["buttons"] += 1

        # ---- plot 1 selects, with the compact menus
        exercise_select(page, rec, "#csel", restore="caaspp_math")
        exercise_select(page, rec, "#ysel", restore="uc_grad4")
        exercise_select(page, rec, "#xsel", restore="gpa_uc")
        exercise_ranges(page, rec)

        # ---- change-over-time axes expose the from/to selects and the cross-section line
        page.select_option("#xsel", "d:caaspp"); settle(page)
        page.select_option("#ysel", "d:caaspp_math"); settle(page)
        for sel in ("#xfrom", "#xto", "#yfrom", "#yto"):
            exercise_select(page, rec, sel)
        page.select_option("#xfrom", "sel"); page.select_option("#yfrom", "sel"); settle(page)
        page.click("input[name=tline][value=xsect]"); settle(page); rec.exercised["checks"] += 1
        exercise_select(page, rec, "#xsyr")
        exercise_ranges(page, rec)

        # ---- same-unit axes enable the equality line
        page.select_option("#xsel", "caaspp"); page.select_option("#ysel", "caaspp_math"); settle(page)
        for v in ("eq", "wols", "ols"):
            page.click("input[name=tline][value=%s]" % v); settle(page); rec.exercised["checks"] += 1
        page.click("#trendchk"); settle(page)      # off
        page.click("#trendchk"); settle(page)      # on again
        rec.exercised["checks"] += 2

        # ---- the full menus
        page.click("#moretoggle"); settle(page); rec.exercised["buttons"] += 1
        page.select_option("#xsel", "gpa_uc"); page.select_option("#ysel", "uc_grad4"); settle(page)
        exercise_select(page, rec, "#csel", restore="caaspp_math")
        exercise_select(page, rec, "#ysel", restore="uc_grad4")
        exercise_select(page, rec, "#xsel", restore="gpa_uc")

        # ---- plot 1 views and canvas
        exercise_plot_buttons(page, rec, 1)
        canvas_interactions(page, rec, page.locator("#psec-1 canvas"))

        # ---- spawn the residual plots down to the page's maximum, exercising each
        max_plots = page.evaluate("() => MAXPLOTS")
        for k in range(1, max_plots):
            page.click("#psec-%d .stack button[data-v=rj]" % k)
            rec.exercised["buttons"] += 1
            page.wait_for_selector("#psec-%d canvas" % (k + 1), timeout=ANIM_TIMEOUT_MS)
            wait_idle(page)
            if page.evaluate("() => chain.length") != k + 1:
                rec.fail("plot %d did not spawn" % (k + 1))
                break
            kk = k + 1
            exercise_select(page, rec, "#pc-%d select" % kk)
            page.click("#pc-%d input[type=checkbox]" % kk); settle(page)
            page.click("#pc-%d input[type=checkbox]" % kk); settle(page)
            rec.exercised["checks"] += 2
            for v in ("wols", "ols"):
                page.click("#pc-%d input[type=radio][value=%s]" % (kk, v)); settle(page)
                rec.exercised["checks"] += 1
            exercise_plot_buttons(page, rec, kk)
            canvas_interactions(page, rec, page.locator("#psec-%d canvas" % kk))
            page.click("#psec-%d .pctl" % kk); settle(page)
            page.click("#psec-%d .pctl" % kk); settle(page)
            rec.exercised["buttons"] += 2
        # the year slider now has to satisfy every plot in the chain
        exercise_ranges(page, rec)
        # the rj button of a plot that has a child removes that child
        if page.evaluate("() => chain.length") >= 3:
            page.click("#psec-2 .stack button[data-v=rj]"); settle(page); rec.exercised["buttons"] += 1
            if page.evaluate("() => chain.length") != 2:
                rec.fail("rj on a parent plot did not remove its child")
            page.click("#psec-2 .stack button[data-v=rj]")
            page.wait_for_selector("#psec-3 canvas", timeout=ANIM_TIMEOUT_MS)
            wait_idle(page)
        # REMOVE THIS PLOT, from the bottom up
        while page.evaluate("() => chain.length") > 1:
            k = page.evaluate("() => chain.length")
            page.click("#psec-%d .pkill" % k); settle(page); rec.exercised["buttons"] += 1
            if page.evaluate("() => chain.length") != k - 1:
                rec.fail("REMOVE THIS PLOT on plot %d did not remove it" % k)
                break
        if page.locator(".plotsec").count() != 1:
            rec.fail("%d plot sections remain after removing the derived plots" % page.locator(".plotsec").count())

        # ---- keyboard activation of the role=button links
        for sel in ("#guidetog", "#moretoggle", "#psec-1 .pctl"):
            page.focus(sel); page.keyboard.press("Enter"); settle(page); rec.exercised["buttons"] += 1
        page.set_viewport_size({"width": 700, "height": 900}); settle(page)   # narrow layout
        page.set_viewport_size({"width": 1280, "height": 900}); settle(page)
        wait_idle(page)
        browser.close()
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    here = Path(__file__).resolve().parent
    ap.add_argument("--html", default=str(here.parent / "index.html"), help="page to open (default: ../index.html)")
    ap.add_argument("--executable-path", default=os.environ.get("RENDER_CHECK_CHROMIUM"),
                    help="Chromium binary to use instead of Playwright's own (or set RENDER_CHECK_CHROMIUM)")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    args = ap.parse_args()
    if not Path(args.html).exists():
        print("no such file: " + args.html)
        return 2
    rec = run(args.html, args.executable_path, headless=not args.headed)
    print("exercised: " + ", ".join("%s=%d" % kv for kv in rec.exercised.items()))
    if rec.problems:
        print("FAIL: %d problem(s)" % len(rec.problems))
        for p in rec.problems:
            print("  " + p)
        return 1
    print("PASS: no console errors, page errors, failed requests or failed assertions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
