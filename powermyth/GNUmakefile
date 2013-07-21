
prefix=/tmp/powermyth
usr=$(prefix)/usr
bin=$(usr)/bin
etc=$(prefix)/etc
sudoers_d=$(etc)/sudoers.d
acpi=$(etc)/acpi
events=$(acpi)/events

INSTALL=install --compare
MV=mv

BIN_FILES=mythwake powerbtn

_etc_sudoers.d_powermyth:
	sed -e 's|$${bin}|$(bin)/|' < $@.orig >$@

_etc_acpi_events_powerbtn:
	sed -e 's|$${bin}|$(bin)/|' < $@.orig >$@

powerbtn:
	sed -e 's|$${bin}|$(bin)/|' < $@.orig >$@

SED_FILES = _etc_sudoers.d_powermyth _etc_acpi_events_powerbtn powerbtn 
.PHONY: $(SED_FILES)

install: $(SED_FILES)
	$(INSTALL) --mode=0440 \
		_etc_sudoers.d_powermyth $(sudoers_d)/powermyth
	$(INSTALL) -d $(bin)/
	$(INSTALL) -D --mode=0755 $(BIN_FILES) $(bin)/
	test -f $(events)/powerbtn \
	  && test '!' -f $(events)/powerbtn.pre_powermyth \
	  && $(MV) $(events)/powerbtn $(events)/powerbtn.pre_powermyth \
	  || :
	$(INSTALL) -D --mode=0644 \
		_etc_acpi_events_powerbtn $(events)/powerbtn

uninstall:
	$(RM) $(sudoers_d)/powermyth
	$(RM) $(addprefix $(bin)/,$(BIN_FILES))
	test -f $(events)/powerbtn.pre_powermyth \
	  && $(MV) $(events)/powerbtn.pre_powermyth $(events)/powerbtn \
	  || $(RM) $(events)/powerbtn
