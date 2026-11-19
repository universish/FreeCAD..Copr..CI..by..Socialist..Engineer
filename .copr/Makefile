srpm:
	set -e; \
	\
	echo "=== Installing build tools ==="; \
	dnf -y install --skip-unavailable rpmdevtools wget curl unzip; \
	\
	echo "=== Fetching latest STABLE release version ==="; \
	VERSION=$$(curl -sfL https://api.github.com/repos/FreeCAD/FreeCAD/releases/latest \
	  | grep '"tag_name"' | cut -d '"' -f 4); \
	if [ -z "$$VERSION" ]; then \
	  echo "ERROR: failed to determine latest version from GitHub API"; \
	  exit 1; \
	fi; \
	echo "Latest version: $${VERSION}"; \
	\
	echo "=== Downloading source tarball ==="; \
	wget -q "https://github.com/FreeCAD/FreeCAD/releases/download/$${VERSION}/freecad_source_$${VERSION}.tar.gz" \
	  -O "freecad_source_$${VERSION}.tar.gz"; \
	ls -lh "freecad_source_$${VERSION}.tar.gz"; \
	\
	echo "=== Preparing rpmbuild tree ==="; \
	rpmdev-setuptree; \
	mkdir -p "$$HOME/rpmbuild/SOURCES" "$$HOME/rpmbuild/SPECS"; \
	cp "freecad_source_$${VERSION}.tar.gz" "$$HOME/rpmbuild/SOURCES/"; \
	cp README.md "$$HOME/rpmbuild/SOURCES/"; \
	\
	echo "=== Copying patches ==="; \
	for p in patches/*.patch; do \
	  if [ -f "$$p" ]; then \
	    cp "$$p" "$$HOME/rpmbuild/SOURCES/"; \
	    echo "  Copied: $$p"; \
	  fi; \
	done; \
	\
	echo "=== Generating spec file from template ==="; \
	test -f freecad.spec || { echo "ERROR: freecad.spec not found in repo root"; exit 1; }; \
	sed -e "s/@VERSION@/$${VERSION}/g" \
	    -e "s/@RELEASE@/1/g" \
	    freecad.spec > "$$HOME/rpmbuild/SPECS/freecad.spec"; \
	\
	echo "=== Building SRPM ==="; \
	rpmbuild -bs \
	  --define "_sourcedir $$HOME/rpmbuild/SOURCES" \
	  --define "_srcrpmdir $(outdir)" \
	  "$$HOME/rpmbuild/SPECS/freecad.spec"; \
	\
	echo "=== Done ==="; \
	ls -la "$(outdir)"

.PHONY: srpm