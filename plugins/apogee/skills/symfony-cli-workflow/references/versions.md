# Versions: 8.1 default, 7.4 LTS and 6.4 LTS differences, upgrade path

Determine the project version before reading further (SKILL.md §1). Dates below follow Symfony's
published schedule; confirm on symfony.com/releases when it matters.

## Contents

1. Support matrix
2. Symfony 8.x conventions (what "modern" means here)
3. Removed in 8.0 / deprecated in 8.1 — common traps
4. Writing for 7.4 LTS
5. Writing for 6.4 LTS
6. Upgrade path 7.4 → 8.x (and 6.4 → 7.4 first)

---

## 1. Support matrix

| Version | Released | Bug fixes until | Security fixes until | PHP | Notes |
|---|---|---|---|---|---|
| 8.1 | May 2026 | ~Jan 2027 | ~Jan 2027 | ≥ 8.4 | current; default for new work |
| 8.0 | Nov 2025 | ~Jul 2026 | ~Jul 2026 | ≥ 8.4 | 7.4 minus deprecations |
| 7.4 LTS | Nov 2025 | Nov 2028 | Nov 2029 | ≥ 8.2 | same features as 8.0, keeps deprecated paths |
| 6.4 LTS | Nov 2023 | Nov 2026 | Nov 2027 | ≥ 8.1 | last version with the old namespaces still working |

Regular minors (x.1, x.2, x.3) get 8 months of fixes; x.4 is the LTS of each major. "What 8.1 adds
over 8.0" is a moving target — do not assert 8.1-only features from memory; read
`vendor/symfony/*/CHANGELOG.md` for the installed components or ask the user to pin the need.

## 2. Symfony 8.x conventions

Generate or hand-write code like this on 8.x projects:

```php
// src/Controller/ProductController.php
namespace App\Controller;

use App\Repository\ProductRepository;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

#[Route('/products', name: 'product_')]
final class ProductController extends AbstractController
{
    public function __construct(private readonly ProductRepository $products) {}

    #[Route('', name: 'index', methods: ['GET'])]
    public function index(): Response
    {
        return $this->render('product/index.html.twig', ['products' => $this->products->findAll()]);
    }
}
```

```php
// src/Command/ImportCommand.php — invokable style (7.3+ / 8.x)
use Symfony\Component\Console\Attribute\{Argument, AsCommand, Option};
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Style\SymfonyStyle;

#[AsCommand(name: 'app:import', description: 'Import products from a CSV file')]
final class ImportCommand
{
    public function __invoke(
        SymfonyStyle $io,
        #[Argument('Path to the CSV')] string $path,
        #[Option('Do not write anything')] bool $dryRun = false,
    ): int {
        // …
        return Command::SUCCESS;
    }
}
```

```php
// src/Entity/Product.php
use Doctrine\ORM\Mapping as ORM;

#[ORM\Entity(repositoryClass: ProductRepository::class)]
class Product
{
    #[ORM\Id, ORM\GeneratedValue, ORM\Column]
    private ?int $id = null;

    #[ORM\Column(length: 255)]
    private ?string $name = null;
}
```

Other defaults: `#[AsEventListener]` over `EventSubscriberInterface` for new listeners;
`#[AsMessageHandler]` on invokable handlers; `#[MapRequestPayload]` / `#[MapQueryString]` /
`#[MapEntity]` for controller input; `#[IsGranted]` and `#[CurrentUser]`; `Symfony\Bundle\SecurityBundle\Security`
for the security helper; `#[Autowire(service:|param:|env:)]` instead of `services.yaml` bindings;
config in whatever format the project already uses (YAML by default, PHP config is fine);
`when@dev/test/prod` sections instead of per-env files. Doctrine ORM 3 / DBAL 4 / DoctrineBundle 3
on 8.x: attributes only, no annotations, `Types::` constants, no `getDoctrine()`.

PHP 8.4 features (property hooks, asymmetric visibility, `new` without parentheses) are available on
8.x projects but check the project's `require.php` and coding standard before using them in
shared code.

## 3. Removed in 8.0 / deprecated in 8.1 — common traps

Anything deprecated throughout 7.x is **gone** in 8.0. If the project is 8.x and you see one of
these in a snippet you are about to paste, stop:

| Do not use | Use |
|---|---|
| `Symfony\Component\Routing\Annotation\Route` (removed 7.0) | `Symfony\Component\Routing\Attribute\Route` |
| annotations of any kind (`@ORM\…`, `@Route`) | PHP attributes |
| `Symfony\Component\Security\Core\Security` (removed 7.0) | `Symfony\Bundle\SecurityBundle\Security` |
| `AbstractController::getDoctrine()` (removed 6.0) | inject `EntityManagerInterface` / a repository |
| `ContainerAwareInterface` / `ContainerAwareTrait` (removed 7.0) | constructor injection |
| `framework.annotations`, `sensio/framework-extra-bundle` | native attributes |
| `security.enable_authenticator_manager`, `anonymous: lazy`, `Guard` authenticators | the new authenticator system (default since 6.0) |
| `Command::$defaultName` / `$defaultDescription` static props (deprecated 6.1, removed 7.0) | `#[AsCommand(name:, description:)]` |
| `configure()`-only commands with string-built `InputArgument`s on 8.x | `#[Argument]`/`#[Option]` invokables (optional, but what Maker emits) |
| `Request::get()` | `$request->attributes/query/request->get()` explicitly (deprecated in 7.x — verify in the installed CHANGELOG) |
| `AnnotationRegistry`, `doctrine/annotations` | drop the dependency |
| `symfony/webpack-encore-bundle` as the *assumed* default | AssetMapper unless the project uses Encore |
| `TreeBuilder` config classes without `ConfigurableExtension` | `AbstractBundle` with `configure()`/`loadExtension()` (6.1+) |

Deprecations introduced *in 8.1 itself* are not listed here on purpose — read `UPGRADE-8.1.md` for
the installed version rather than trusting a static list. Run
`symfony console debug:container --deprecations` after a `cache:clear` to see what the project's own
code triggers.

## 4. Writing for 7.4 LTS

Treat as 8.0 with the deprecated code still present. Everything in §2 works unchanged (attributes,
invokable commands since 7.3, `MapRequestPayload`, AssetMapper). Differences that matter:

- PHP ≥ 8.2 is enough; do not use PHP 8.4-only syntax unless `require.php` says `>=8.4`.
- Deprecated APIs still *run* but log deprecations — do not add new usages; they block the 8.x upgrade.
- Flex `extra.symfony.require` is `"7.4.*"`; `symfony composer require` will not pull 8.x packages,
  so Maker/bundle versions may lag — look at what `make:*` generates rather than assuming.
- 7.4 is the version to park on when a dependency has no 8.x release yet. Say so instead of
  forcing the upgrade.

## 5. Writing for 6.4 LTS

- PHP ≥ 8.1. Doctrine may still be ORM 2.x / DBAL 3 — check `composer.lock` before using
  `Types::` constants or ORM 3-only features.
- Both `Routing\Annotation\Route` and `Routing\Attribute\Route` exist; **write the `Attribute` one**
  so the code survives 7.0.
- No invokable commands with `#[Argument]`/`#[Option]` (that is 7.3+). Use
  `#[AsCommand]` + `extends Command` + `configure()`/`execute()`.
- `#[MapRequestPayload]`/`#[MapQueryString]` exist (6.3+); `#[MapUploadedFile]` does not (7.1).
- AssetMapper exists (6.3+, default in 6.4 webapp) but many 6.4 projects still ship Encore. Follow
  the project.
- `Symfony\Bundle\SecurityBundle\Security` exists (6.2+); use it, not the deprecated Core one.
- Run `symfony console debug:container --deprecations` before suggesting an upgrade; the 6.4 → 7.4
  path is identical in shape to §6.

## 6. Upgrade path

Only on an explicit request, and after the user has a green test suite and a clean git state. Majors
are reached through the LTS below them: 6.4 → 7.4 → 8.x; never jump 6.4 → 8.x.

1. **Latest patch of the current LTS**: `symfony composer update "symfony/*"`; run tests.
2. **Zero deprecations**: `symfony console debug:container --deprecations`; profiler Deprecations
   panel on key pages; `SYMFONY_DEPRECATIONS_HELPER='max[self]=0&max[direct]=0' symfony php bin/phpunit`.
   Fix each in your code; for vendor deprecations, bump the vendor package.
3. **PHP**: 8.x needs 8.4+. `symfony local:php:list`, `echo 8.4 > .php-version`, update
   `require.php` and CI images.
4. **Read the UPGRADE files** for the target (`UPGRADE-8.0.md` lists every removal by component;
   `UPGRADE-8.1.md` lists new deprecations). Check third-party bundles:
   `symfony composer why-not symfony/framework-bundle 8.1`.
5. **Switch**: set `extra.symfony.require` to `"8.1.*"`, `symfony composer update "symfony/*" --with-all-dependencies`.
   Expect Composer to name the blockers; resolve them one at a time.
6. **Recipes and config**: `symfony composer recipes:update` (review each diff),
   `symfony console lint:container`, `cache:warmup --env=prod`, `lint:yaml config/`.
7. **Full test run**, then `symfony console about` to confirm the version. Commit the upgrade on
   its own; do not bundle features into it.

Doctrine-specific: ORM 2 → 3 and DBAL 3 → 4 usually land with the same `composer update`; read
`vendor/doctrine/orm/UPGRADE.md` as well.
