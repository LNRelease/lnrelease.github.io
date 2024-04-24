(() => {
    if (!document.currentScript) return;

    let cache;

    async function track(_, name = '', type = 'event') {
        try {
            const res = await fetch('https://analytics.eu.umami.is/api/send', {
                body: JSON.stringify({
                    type: type,
                    payload: {
                        hostname: location.hostname,
                        language: navigator.language,
                        referrer: encodeURI(document.referrer),
                        screen: `${screen.width}x${screen.height}`,
                        title: encodeURI(document.title),
                        url: encodeURI(location.pathname + location.search),
                        website: 'bdb27612-e23d-4bec-9a55-0c4ce58944f3',
                        ...(name && { name: name }),
                    }
                }),
                headers: {
                    'Content-Type': 'application/json',
                    ...(cache && { 'x-umami-cache': cache }),
                },
                keepalive: true,
                method: 'POST',
            });
            cache = await res.text();
        } catch {
            /* empty */
        }
    };

    document.readyState === 'complete' ? track() :
        document.addEventListener('readystatechange', track, { once: true });
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
            track(null, 'hide');
        }
    });

})();
