# Design

The demo page and the launch video share one direction. Change it here first.

## Concept

callgrade started as a scoring sheet filled in by hand: seven rows, 0 to 2 each.
So the page is that sheet, printed as a carbonless multi-part form. Form ink
prints the template. The machine types the answers in. The judge's three runs
are the form's three copies, white, canary and pink, and the page is about the
places where the copies disagree.

## Tokens

The palette is the original warm paper and rust, kept by choice. The form ink is
the rust, the way some carbon forms are printed in red-brown ink.

| Role | Light | Dark |
|---|---|---|
| Sheet | `#f3eee3` | `#161411` |
| Typed answers | `#1b1813` | `#e9e2d3` |
| Form ink: labels, rules, links, the agent's bars | `#b23a16` | `#e8743f` |
| Caller's bars | `#4c5566` | `#a9b1c3` |
| Pass, caught | `#2a6b3f` | `#6cc48a` |
| Stamp: fail, missed, a 0 | `#a9281b` | `#ef6b63` |
| Copy 2 (canary) | `#f1e5b6` | `#2a2516` |
| Copy 3 (pink) | `#f0d8d0` | `#2c1d1b` |
| Green-bar printout | `#e3e8d6` | `#1b2118` |

## Type

- **Archivo** for everything printed on the form. Field labels use it at 75% width,
  weight 600, in form ink, sentence case. No tracked capitals.
- **Courier Prime** for everything filled in: transcripts, judge reasons, scores, commands.

## Pieces

- **Field box.** A ruled box with a small label in its top-left corner. Stats, the
  install line and remarks are all field boxes.
- **Bubbles.** Scores 0, 1, 2 are answer-sheet bubbles. The chosen one is filled,
  and a 0 is filled in stamp red.
- **Stamp.** Bordered, uppercase, rotated a few degrees. Used for the band verdict
  and for "reason says 0". Nowhere else.
- **Copies.** Anything shown per run is tinted by copy colour: run 1 white, run 2
  canary, run 3 pink.
- **Green-bar paper.** CLI output sits on continuous-feed paper with tractor holes.

## Don't

A serif newspaper layout, numbered sections, an accented word in the headline,
monospace all-caps labels, cards. The first redesign used all of these. The
warm paper and rust stayed because they were liked, not by default.

The launch video keeps the earlier serif look on purpose. It was preferred.
