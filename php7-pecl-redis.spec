# spec file for php-pecl-redis
#
# Copyright (c) 2012-2014 Remi Collet
# License: CC-BY-SA
# http://creativecommons.org/licenses/by-sa/3.0/
#
# Please, preserve the changelog entries
#
%{!?php_inidir:  %global php_inidir  %{_sysconfdir}/php.d}
%{!?__pecl:      %global __pecl      %{_bindir}/pecl}
%{!?__php:       %global __php       %{_bindir}/php}

%global basepkg     %{?basepkg}%{!?basepkg:php}
%global pecl_name   redis
%global with_zts    0%{?__ztsphp:1}
%global with_tests  %{?_with_tests:1}%{!?_with_tests:0}

%global with_igbinary 0

Summary:       Extension for communicating with the Redis key-value store
Name:          %{basepkg}-pecl-redis
Version:       3.0.0
Release:       1%{?dist}
License:       PHP
Group:         Development/Languages
URL:           http://pecl.php.net/package/redis
Source0:       http://pecl.php.net/get/%{pecl_name}-%{version}.tgz

BuildRoot:     %{_tmppath}/%{name}-%{version}-%{release}-root
BuildRequires: %{basepkg}-devel
%if 0%{?with_igbinary}
BuildRequires: %{basepkg}-pecl-igbinary-devel
%endif
# to run Test suite
%if %{with_tests}
BuildRequires: redis >= 2.6
%endif

Requires:      php(zend-abi) = %{php_zend_api}
Requires:      php(api) = %{php_core_api}
%if 0%{?with_igbinary}
# php-pecl-igbinary missing php-pecl(igbinary)%{?_isa}
Requires:      php-pecl-igbinary%{?_isa}
%endif
Provides:      php-redis = %{version}-%{release}
Provides:      php-redis%{?_isa} = %{version}-%{release}
Provides:      php-pecl(%{pecl_name}) = %{version}
Provides:      php-pecl(%{pecl_name})%{?_isa} = %{version}
Provides:      php-pecl-%{pecl_name} = %{version}-%{release}
Provides:      php-pecl-%{pecl_name}%{?_isa} = %{version}-%{release}

%if 0%{?fedora} < 20 && 0%{?rhel} < 7
# Filter private shared object
%{?filter_provides_in: %filter_provides_in %{_libdir}/.*\.so$}
%{?filter_setup}
%endif


%description
The phpredis extension provides an API for communicating
with the Redis key-value store.

This Redis client implements most of the latest Redis API.
As method only only works when also implemented on the server side,
some doesn't work with an old redis server version.


%prep
%setup -q -c

# rename source folder
mv %{pecl_name}-%{version} nts

# Sanity check, really often broken
extver=$(sed -n '/#define PHP_REDIS_VERSION/{s/.* "//;s/".*$//;p}' nts/php_redis.h)
if test "x${extver}" != "x%{version}"; then
   : Error: Upstream extension version is ${extver}, expecting %{version}.
   exit 1
fi

%if %{with_zts}
# duplicate for ZTS build
cp -pr nts zts
%endif

# Drop in the bit of configuration
cat > %{pecl_name}.ini << 'EOF'
; Enable %{pecl_name} extension module
extension = %{pecl_name}.so

; phpredis can be used to store PHP sessions. 
; To do this, uncomment and configure below
;session.save_handler = %{pecl_name}
;session.save_path = "tcp://host1:6379?weight=1, tcp://host2:6379?weight=2&timeout=2.5, tcp://host3:6379?weight=2"
EOF


%build
cd nts
%{_bindir}/phpize
%configure \
    --enable-redis \
    --enable-redis-session \
%if 0%{?with_igbinary}
    --enable-redis-igbinary \
%endif
    --with-php-config=%{_bindir}/php-config
make %{?_smp_mflags}

%if %{with_zts}
cd ../zts
%{_bindir}/zts-phpize
%configure \
    --enable-redis \
    --enable-redis-session \
%if 0%{?with_igbinary}
    --enable-redis-igbinary \
%endif
    --with-php-config=%{_bindir}/zts-php-config
make %{?_smp_mflags}
%endif


%install
# Install the NTS stuff
make -C nts install INSTALL_ROOT=%{buildroot}
install -D -m 644 %{pecl_name}.ini %{buildroot}%{php_inidir}/%{pecl_name}.ini

%if %{with_zts}
# Install the ZTS stuff
make -C zts install INSTALL_ROOT=%{buildroot}
install -D -m 644 %{pecl_name}.ini %{buildroot}%{php_ztsinidir}/%{pecl_name}.ini
%endif

# Install the package XML file
install -D -m 644 package.xml %{buildroot}%{pecl_xmldir}/%{name}.xml

# Test & Documentation
cd nts
for i in $(grep 'role="doc"' ../package.xml | sed -e 's/^.*name="//;s/".*$//')
do install -Dpm 644 $i %{buildroot}%{pecl_docdir}/%{pecl_name}/$i
done


%check
# simple module load test
%{__php} --no-php-ini \
%if 0%{?with_igbinary}
    --define extension=igbinary.so \
%endif
    --define extension=%{buildroot}%{php_extdir}/%{pecl_name}.so \
    --modules | grep %{pecl_name}

%if %{with_zts}
%{__ztsphp} --no-php-ini \
%if 0%{?with_igbinary}
    --define extension=igbinary.so \
%endif
    --define extension=%{buildroot}%{php_ztsextdir}/%{pecl_name}.so \
    --modules | grep %{pecl_name}
%endif

%if %{with_tests}
cd nts/tests

# this test requires redis >= 2.6.9
# https://github.com/nicolasff/phpredis/pull/333
sed -e s/testClient/SKIP_testClient/ \
    -i TestRedis.php

# Launch redis server
mkdir -p {run,log,lib}/redis
sed -e "s:/var:$PWD:" \
    -e "/daemonize/s/no/yes/" \
    /etc/redis.conf >redis.conf
# port number to allow 32/64 build at same time
# and avoid conflict with a possible running server
%if 0%{?__isa_bits}
port=$(expr %{__isa_bits} + 6350)
%else
%ifarch x86_64
port=6414
%else
port=6382
%endif
%endif
sed -e "s/6379/$port/" -i redis.conf
sed -e "s/6379/$port/" -i TestRedis.php
%{_sbindir}/redis-server ./redis.conf

# Run the test Suite
ret=0
%{__php} --no-php-ini \
%if 0%{?with_igbinary}
    --define extension=igbinary.so \
%endif
    --define extension=%{buildroot}%{php_extdir}/%{pecl_name}.so \
    TestRedis.php || ret=1

# Cleanup
if [ -f run/redis/redis.pid ]; then
   kill $(cat run/redis/redis.pid)
fi

exit $ret

%else
: Upstream test suite disabled
%endif


%post
%{pecl_install} %{pecl_xmldir}/%{name}.xml >/dev/null || :


%postun
if [ $1 -eq 0 ] ; then
    %{pecl_uninstall} %{pecl_name} >/dev/null || :
fi


%files
%doc %{pecl_docdir}/%{pecl_name}
%{pecl_xmldir}/%{name}.xml

%{php_extdir}/%{pecl_name}.so
%config(noreplace) %{php_inidir}/%{pecl_name}.ini

%if %{with_zts}
%{php_ztsextdir}/%{pecl_name}.so
%config(noreplace) %{php_ztsinidir}/%{pecl_name}.ini
%endif


%changelog
* Tue Jun 21 2016 Andy Thompson <andy@webtatic.com> - 3.0.0-1
- Update to 3.0.0
- Remove SOURCE1 now upstream pecl package has tests
- Disable igbinary support until upstream ready for PHP 7

* Wed Apr 08 2015 Andy Thompson <andy@webtatic.com> - 2.2.7-1
- Update to 2.2.7

* Sat Sep 13 2014 Andy Thompson <andy@webtatic.com> - 2.2.5-1
- Import EPEL7 php-pecl-redis-2.2.5-1 RPM
