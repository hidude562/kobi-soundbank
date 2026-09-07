# kobi soundbank — reproduce every bank from the pulled sources.
#
#   make deps            the dctloop/dctjoin library (git submodule) and python packages
#   make test            unit tests (python + node)
#   make banks           the three compressed banks from the sources        (~1 h each)
#   make finish          per-note balance, programme levels, key extension  (~15 min each)
#   make derive          the six slim / ultra banks from the compressed ones (~30 min)
#   make index           byte-range indexes and manifests for the web players
#   make demos           the demo MIDIs rendered through sfizz from kobi_slim
#   make web-test        the browser tests (Chromium via playwright)
#   make serve           a Range-capable static server for the web players on :8080
#
# Paths come from kobi/paths.py (KOBI_ROOT, KOBI_SOURCES, KOBI_SSO, KOBI_DCTJOIN, KOBI_MIDIS).
PY ?= python3
J  ?= 3
FULL = kobi_ogg kobi_ogg_lite kobi_ogg_lite25
DERIVED = kobi_slim kobi_slim_lite kobi_slim_lite25 kobi_ultra kobi_ultra_hifi kobi_ultra_hifi_pf
ALL = $(FULL) $(DERIVED)

.PHONY: all deps test banks finish derive index demos web-test serve clean-outputs

all: banks finish derive index

deps:
	git submodule update --init
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest kobi/tests -q
	cd kobi_web && node --test test/parsers.test.mjs && node --test test/sched.test.mjs

# the compressed banks: full (0.5 s loops), lite (0.2 s loops, short sustain attacks), lite25 (short attacks everywhere)
banks:
	$(PY) -m kobi.compress --all --loop 0.5 --attack 0.5  --decay-attack 1.0  --decay-bridge 0.85 -j $(J) --out kobi_ogg
	$(PY) -m kobi.compress --all --loop 0.2 --attack 0.25 --decay-attack 1.0  --decay-bridge 0.85 -j $(J) --out kobi_ogg_lite
	$(PY) -m kobi.compress --all --loop 0.2 --attack 0.25 --decay-attack 0.25 --decay-bridge 0.18 -j $(J) --out kobi_ogg_lite25

# every note of a programme at the programme's loudness, every programme at -23 LUFS, every key covered
finish:
	for b in $(FULL); do \
	  $(PY) -m kobi.balance $$b --clamp 60 && \
	  $(PY) -m kobi.levels --bank $$b/GM --max-gain 80 && mv $$b/GM/LEVELS.md $$b/LEVELS.md && \
	  $(PY) -m kobi.extend $$b || exit 1; \
	done

derive:
	$(PY) -m kobi.slim --src kobi_ogg        --out kobi_slim        --target-mb 25
	$(PY) -m kobi.slim --src kobi_ogg_lite   --out kobi_slim_lite   --target-mb 25
	$(PY) -m kobi.slim --src kobi_ogg_lite25 --out kobi_slim_lite25 --target-mb 25
	$(PY) -m kobi.slim --src kobi_ogg_lite25 --out kobi_ultra       --target-mb 5
	$(PY) -m kobi.slim --src kobi_ogg_lite25 --out kobi_ultra_hifi  --target-mb 5 --max-vel 1 --codec-step 4
	$(PY) -m kobi.postfilter --src kobi_ogg_lite25 --out kobi_ultra_hifi_pf --min-space 5 --max-vel 1 --rate-div 2 -q 0.0 --sfx-notes 1

index:
	$(PY) -m kobi.slices $(ALL) --verify --sample 0.05
	$(PY) -m kobi.manifest $(ALL)

demos:
	mkdir -p renders_slim
	cd vendor/sfz_compressor 2>/dev/null || cd $$(KOBI_ROOT=$(CURDIR) $(PY) -c 'from kobi import paths; print(paths.dctjoin_dir())'); \
	for f in "$(CURDIR)"/midi/nena/*.[mM][iI][dD]*; do b=$$(basename "$$f"); \
	  $(PY) -m dctjoin.gm render "$$f" "$(CURDIR)/renders_slim/$${b%.*}.wav" --bank $(CURDIR)/kobi_slim/GM; done

web-test:
	$(PY) kobi_web/test/smoke_browser.py
	$(PY) kobi_web/test/peaks_browser.py
	$(PY) kobi_web/test/splice_browser.py kobi_slim 000_Acoustic_Grand_Piano
	$(PY) kobi_web/test/sched_browser.py 07COUNT kobi_slim 20

serve:
	$(PY) kobi_web/test/rangeserver.py 8080 $(CURDIR)

# rendered demos and auditions are regenerable; the banks are not deleted
clean-outputs:
	rm -rf renders renders_* demo demo_* logs
