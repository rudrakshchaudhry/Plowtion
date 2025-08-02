import Link from "next/link";

export default function Footer() {
    const navItems = [
        { title: 'Home', link: '/' },
        { title: 'Marketplace', link: '/marketplace' },
        { title: 'Crop Guide', link: '/crops' },
    ];

    const resources = [
        { title: 'Privacy Policy', link: '/privacy' },
        { title: 'Terms of Service', link: '/terms' },
    ];

    return (
        <section className="bg-gray-100 text-gray-800">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                    <div className="col-span-1 md:col-span-2">
                        <h2 className="text-2xl font-bold mb-4">FarmNest</h2>
                        <p className="text-sm mb-4">Connect, grow, and succeed with FarmNest - your one stop farming guide.</p>
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold mb-4">Navigation</h3>
                        <ul className="space-y-2">
                            {navItems.map((item, index) => (
                                <li key={index}>
                                    <Link href={item.link} className="text-gray-600 hover:text-gray-900">
                                        {item.title}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold mb-4">Resources</h3>
                        <ul className="space-y-2">
                            {resources.map((item, index) => (
                                <li key={index}>
                                    <Link href={item.link} className="text-gray-600 hover:text-gray-900">
                                        {item.title}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
                <div className="mt-12 pt-8 border-t border-gray-200">
                    <div className="flex flex-col md:flex-row justify-between items-center">
                        <p className="text-sm text-gray-600">&copy; {new Date().getFullYear()} FarmNest. All rights reserved.</p>
                    </div>
                </div>
            </div>
        </section>
    );
}