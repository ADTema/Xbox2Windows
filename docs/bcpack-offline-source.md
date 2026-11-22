# BCPack offline source listings

This appendix preserves the complete, human-readable inputs to the two documented export measurements and all twelve synthetic tests. The seven files from ItsNotRexed/Leonida revision `b0befb4b88d6640354940117448ea19d52507584` retain the upstream GNU General Public License version 3. The optional calibration module is timelery/Leonida's `tools/bcpack_tables_bptc.py` from revision `3c997c411666b31372b0d2b82afd5ea669b4d774`, preserved under the filename `history_snapshot.py`. The license text below applies to the archived sources. Retain it with extracted copies.

The [reproduction guide](bcpack-archive-reproduction.md) includes commands to extract and verify these listings using Python. Each digest covers the original UTF-8 file with LF line endings, including its last newline. Original comments, executable tests, constants and imports are preserved.

## LICENSE

SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`

````text
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU General Public License is a free, copyleft license for
software and other kinds of works.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
the GNU General Public License is intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.  We, the Free Software Foundation, use the
GNU General Public License for most of our software; it applies also to
any other work released this way by its authors.  You can apply it to
your programs, too.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  To protect your rights, we need to prevent others from denying you
these rights or asking you to surrender the rights.  Therefore, you have
certain responsibilities if you distribute copies of the software, or if
you modify it: responsibilities to respect the freedom of others.

  For example, if you distribute copies of such a program, whether
gratis or for a fee, you must pass on to the recipients the same
freedoms that you received.  You must make sure that they, too, receive
or can get the source code.  And you must show them these terms so they
know their rights.

  Developers that use the GNU GPL protect your rights with two steps:
(1) assert copyright on the software, and (2) offer you this License
giving you legal permission to copy, distribute and/or modify it.

  For the developers' and authors' protection, the GPL clearly explains
that there is no warranty for this free software.  For both users' and
authors' sake, the GPL requires that modified versions be marked as
changed, so that their problems will not be attributed erroneously to
authors of previous versions.

  Some devices are designed to deny users access to install or run
modified versions of the software inside them, although the manufacturer
can do so.  This is fundamentally incompatible with the aim of
protecting users' freedom to change the software.  The systematic
pattern of such abuse occurs in the area of products for individuals to
use, which is precisely where it is most unacceptable.  Therefore, we
have designed this version of the GPL to prohibit the practice for those
products.  If such problems arise substantially in other domains, we
stand ready to extend this provision to those domains in future versions
of the GPL, as needed to protect the freedom of users.

  Finally, every program is threatened constantly by software patents.
States should not allow patents to restrict development and use of
software on general-purpose computers, but in those that do, we wish to
avoid the special danger that patents applied to a free program could
make it effectively proprietary.  To prevent this, the GPL assures that
patents cannot be used to render the program non-free.

  The precise terms and conditions for copying, distribution and
modification follow.

                       TERMS AND CONDITIONS

  0. Definitions.

  "This License" refers to version 3 of the GNU General Public License.

  "Copyright" also means copyright-like laws that apply to other kinds of
works, such as semiconductor masks.

  "The Program" refers to any copyrightable work licensed under this
License.  Each licensee is addressed as "you".  "Licensees" and
"recipients" may be individuals or organizations.

  To "modify" a work means to copy from or adapt all or part of the work
in a fashion requiring copyright permission, other than the making of an
exact copy.  The resulting work is called a "modified version" of the
earlier work or a work "based on" the earlier work.

  A "covered work" means either the unmodified Program or a work based
on the Program.

  To "propagate" a work means to do anything with it that, without
permission, would make you directly or secondarily liable for
infringement under applicable copyright law, except executing it on a
computer or modifying a private copy.  Propagation includes copying,
distribution (with or without modification), making available to the
public, and in some countries other activities as well.

  To "convey" a work means any kind of propagation that enables other
parties to make or receive copies.  Mere interaction with a user through
a computer network, with no transfer of a copy, is not conveying.

  An interactive user interface displays "Appropriate Legal Notices"
to the extent that it includes a convenient and prominently visible
feature that (1) displays an appropriate copyright notice, and (2)
tells the user that there is no warranty for the work (except to the
extent that warranties are provided), that licensees may convey the
work under this License, and how to view a copy of this License.  If
the interface presents a list of user commands or options, such as a
menu, a prominent item in the list meets this criterion.

  1. Source Code.

  The "source code" for a work means the preferred form of the work
for making modifications to it.  "Object code" means any non-source
form of a work.

  A "Standard Interface" means an interface that either is an official
standard defined by a recognized standards body, or, in the case of
interfaces specified for a particular programming language, one that
is widely used among developers working in that language.

  The "System Libraries" of an executable work include anything, other
than the work as a whole, that (a) is included in the normal form of
packaging a Major Component, but which is not part of that Major
Component, and (b) serves only to enable use of the work with that
Major Component, or to implement a Standard Interface for which an
implementation is available to the public in source code form.  A
"Major Component", in this context, means a major essential component
(kernel, window system, and so on) of the specific operating system
(if any) on which the executable work runs, or a compiler used to
produce the work, or an object code interpreter used to run it.

  The "Corresponding Source" for a work in object code form means all
the source code needed to generate, install, and (for an executable
work) run the object code and to modify the work, including scripts to
control those activities.  However, it does not include the work's
System Libraries, or general-purpose tools or generally available free
programs which are used unmodified in performing those activities but
which are not part of the work.  For example, Corresponding Source
includes interface definition files associated with source files for
the work, and the source code for shared libraries and dynamically
linked subprograms that the work is specifically designed to require,
such as by intimate data communication or control flow between those
subprograms and other parts of the work.

  The Corresponding Source need not include anything that users
can regenerate automatically from other parts of the Corresponding
Source.

  The Corresponding Source for a work in source code form is that
same work.

  2. Basic Permissions.

  All rights granted under this License are granted for the term of
copyright on the Program, and are irrevocable provided the stated
conditions are met.  This License explicitly affirms your unlimited
permission to run the unmodified Program.  The output from running a
covered work is covered by this License only if the output, given its
content, constitutes a covered work.  This License acknowledges your
rights of fair use or other equivalent, as provided by copyright law.

  You may make, run and propagate covered works that you do not
convey, without conditions so long as your license otherwise remains
in force.  You may convey covered works to others for the sole purpose
of having them make modifications exclusively for you, or provide you
with facilities for running those works, provided that you comply with
the terms of this License in conveying all material for which you do
not control copyright.  Those thus making or running the covered works
for you must do so exclusively on your behalf, under your direction
and control, on terms that prohibit them from making any copies of
your copyrighted material outside their relationship with you.

  Conveying under any other circumstances is permitted solely under
the conditions stated below.  Sublicensing is not allowed; section 10
makes it unnecessary.

  3. Protecting Users' Legal Rights From Anti-Circumvention Law.

  No covered work shall be deemed part of an effective technological
measure under any applicable law fulfilling obligations under article
11 of the WIPO copyright treaty adopted on 20 December 1996, or
similar laws prohibiting or restricting circumvention of such
measures.

  When you convey a covered work, you waive any legal power to forbid
circumvention of technological measures to the extent such circumvention
is effected by exercising rights under this License with respect to
the covered work, and you disclaim any intention to limit operation or
modification of the work as a means of enforcing, against the work's
users, your or third parties' legal rights to forbid circumvention of
technological measures.

  4. Conveying Verbatim Copies.

  You may convey verbatim copies of the Program's source code as you
receive it, in any medium, provided that you conspicuously and
appropriately publish on each copy an appropriate copyright notice;
keep intact all notices stating that this License and any
non-permissive terms added in accord with section 7 apply to the code;
keep intact all notices of the absence of any warranty; and give all
recipients a copy of this License along with the Program.

  You may charge any price or no price for each copy that you convey,
and you may offer support or warranty protection for a fee.

  5. Conveying Modified Source Versions.

  You may convey a work based on the Program, or the modifications to
produce it from the Program, in the form of source code under the
terms of section 4, provided that you also meet all of these conditions:

    a) The work must carry prominent notices stating that you modified
    it, and giving a relevant date.

    b) The work must carry prominent notices stating that it is
    released under this License and any conditions added under section
    7.  This requirement modifies the requirement in section 4 to
    "keep intact all notices".

    c) You must license the entire work, as a whole, under this
    License to anyone who comes into possession of a copy.  This
    License will therefore apply, along with any applicable section 7
    additional terms, to the whole of the work, and all its parts,
    regardless of how they are packaged.  This License gives no
    permission to license the work in any other way, but it does not
    invalidate such permission if you have separately received it.

    d) If the work has interactive user interfaces, each must display
    Appropriate Legal Notices; however, if the Program has interactive
    interfaces that do not display Appropriate Legal Notices, your
    work need not make them do so.

  A compilation of a covered work with other separate and independent
works, which are not by their nature extensions of the covered work,
and which are not combined with it such as to form a larger program,
in or on a volume of a storage or distribution medium, is called an
"aggregate" if the compilation and its resulting copyright are not
used to limit the access or legal rights of the compilation's users
beyond what the individual works permit.  Inclusion of a covered work
in an aggregate does not cause this License to apply to the other
parts of the aggregate.

  6. Conveying Non-Source Forms.

  You may convey a covered work in object code form under the terms
of sections 4 and 5, provided that you also convey the
machine-readable Corresponding Source under the terms of this License,
in one of these ways:

    a) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by the
    Corresponding Source fixed on a durable physical medium
    customarily used for software interchange.

    b) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by a
    written offer, valid for at least three years and valid for as
    long as you offer spare parts or customer support for that product
    model, to give anyone who possesses the object code either (1) a
    copy of the Corresponding Source for all the software in the
    product that is covered by this License, on a durable physical
    medium customarily used for software interchange, for a price no
    more than your reasonable cost of physically performing this
    conveying of source, or (2) access to copy the
    Corresponding Source from a network server at no charge.

    c) Convey individual copies of the object code with a copy of the
    written offer to provide the Corresponding Source.  This
    alternative is allowed only occasionally and noncommercially, and
    only if you received the object code with such an offer, in accord
    with subsection 6b.

    d) Convey the object code by offering access from a designated
    place (gratis or for a charge), and offer equivalent access to the
    Corresponding Source in the same way through the same place at no
    further charge.  You need not require recipients to copy the
    Corresponding Source along with the object code.  If the place to
    copy the object code is a network server, the Corresponding Source
    may be on a different server (operated by you or a third party)
    that supports equivalent copying facilities, provided you maintain
    clear directions next to the object code saying where to find the
    Corresponding Source.  Regardless of what server hosts the
    Corresponding Source, you remain obligated to ensure that it is
    available for as long as needed to satisfy these requirements.

    e) Convey the object code using peer-to-peer transmission, provided
    you inform other peers where the object code and Corresponding
    Source of the work are being offered to the general public at no
    charge under subsection 6d.

  A separable portion of the object code, whose source code is excluded
from the Corresponding Source as a System Library, need not be
included in conveying the object code work.

  A "User Product" is either (1) a "consumer product", which means any
tangible personal property which is normally used for personal, family,
or household purposes, or (2) anything designed or sold for incorporation
into a dwelling.  In determining whether a product is a consumer product,
doubtful cases shall be resolved in favor of coverage.  For a particular
product received by a particular user, "normally used" refers to a
typical or common use of that class of product, regardless of the status
of the particular user or of the way in which the particular user
actually uses, or expects or is expected to use, the product.  A product
is a consumer product regardless of whether the product has substantial
commercial, industrial or non-consumer uses, unless such uses represent
the only significant mode of use of the product.

  "Installation Information" for a User Product means any methods,
procedures, authorization keys, or other information required to install
and execute modified versions of a covered work in that User Product from
a modified version of its Corresponding Source.  The information must
suffice to ensure that the continued functioning of the modified object
code is in no case prevented or interfered with solely because
modification has been made.

  If you convey an object code work under this section in, or with, or
specifically for use in, a User Product, and the conveying occurs as
part of a transaction in which the right of possession and use of the
User Product is transferred to the recipient in perpetuity or for a
fixed term (regardless of how the transaction is characterized), the
Corresponding Source conveyed under this section must be accompanied
by the Installation Information.  But this requirement does not apply
if neither you nor any third party retains the ability to install
modified object code on the User Product (for example, the work has
been installed in ROM).

  The requirement to provide Installation Information does not include a
requirement to continue to provide support service, warranty, or updates
for a work that has been modified or installed by the recipient, or for
the User Product in which it has been modified or installed.  Access to a
network may be denied when the modification itself materially and
adversely affects the operation of the network or violates the rules and
protocols for communication across the network.

  Corresponding Source conveyed, and Installation Information provided,
in accord with this section must be in a format that is publicly
documented (and with an implementation available to the public in
source code form), and must require no special password or key for
unpacking, reading or copying.

  7. Additional Terms.

  "Additional permissions" are terms that supplement the terms of this
License by making exceptions from one or more of its conditions.
Additional permissions that are applicable to the entire Program shall
be treated as though they were included in this License, to the extent
that they are valid under applicable law.  If additional permissions
apply only to part of the Program, that part may be used separately
under those permissions, but the entire Program remains governed by
this License without regard to the additional permissions.

  When you convey a copy of a covered work, you may at your option
remove any additional permissions from that copy, or from any part of
it.  (Additional permissions may be written to require their own
removal in certain cases when you modify the work.)  You may place
additional permissions on material, added by you to a covered work,
for which you have or can give appropriate copyright permission.

  Notwithstanding any other provision of this License, for material you
add to a covered work, you may (if authorized by the copyright holders of
that material) supplement the terms of this License with terms:

    a) Disclaiming warranty or limiting liability differently from the
    terms of sections 15 and 16 of this License; or

    b) Requiring preservation of specified reasonable legal notices or
    author attributions in that material or in the Appropriate Legal
    Notices displayed by works containing it; or

    c) Prohibiting misrepresentation of the origin of that material, or
    requiring that modified versions of such material be marked in
    reasonable ways as different from the original version; or

    d) Limiting the use for publicity purposes of names of licensors or
    authors of the material; or

    e) Declining to grant rights under trademark law for use of some
    trade names, trademarks, or service marks; or

    f) Requiring indemnification of licensors and authors of that
    material by anyone who conveys the material (or modified versions of
    it) with contractual assumptions of liability to the recipient, for
    any liability that these contractual assumptions directly impose on
    those licensors and authors.

  All other non-permissive additional terms are considered "further
restrictions" within the meaning of section 10.  If the Program as you
received it, or any part of it, contains a notice stating that it is
governed by this License along with a term that is a further
restriction, you may remove that term.  If a license document contains
a further restriction but permits relicensing or conveying under this
License, you may add to a covered work material governed by the terms
of that license document, provided that the further restriction does
not survive such relicensing or conveying.

  If you add terms to a covered work in accord with this section, you
must place, in the relevant source files, a statement of the
additional terms that apply to those files, or a notice indicating
where to find the applicable terms.

  Additional terms, permissive or non-permissive, may be stated in the
form of a separately written license, or stated as exceptions;
the above requirements apply either way.

  8. Termination.

  You may not propagate or modify a covered work except as expressly
provided under this License.  Any attempt otherwise to propagate or
modify it is void, and will automatically terminate your rights under
this License (including any patent licenses granted under the third
paragraph of section 11).

  However, if you cease all violation of this License, then your
license from a particular copyright holder is reinstated (a)
provisionally, unless and until the copyright holder explicitly and
finally terminates your license, and (b) permanently, if the copyright
holder fails to notify you of the violation by some reasonable means
prior to 60 days after the cessation.

  Moreover, your license from a particular copyright holder is
reinstated permanently if the copyright holder notifies you of the
violation by some reasonable means, this is the first time you have
received notice of violation of this License (for any work) from that
copyright holder, and you cure the violation prior to 30 days after
your receipt of the notice.

  Termination of your rights under this section does not terminate the
licenses of parties who have received copies or rights from you under
this License.  If your rights have been terminated and not permanently
reinstated, you do not qualify to receive new licenses for the same
material under section 10.

  9. Acceptance Not Required for Having Copies.

  You are not required to accept this License in order to receive or
run a copy of the Program.  Ancillary propagation of a covered work
occurring solely as a consequence of using peer-to-peer transmission
to receive a copy likewise does not require acceptance.  However,
nothing other than this License grants you permission to propagate or
modify any covered work.  These actions infringe copyright if you do
not accept this License.  Therefore, by modifying or propagating a
covered work, you indicate your acceptance of this License to do so.

  10. Automatic Licensing of Downstream Recipients.

  Each time you convey a covered work, the recipient automatically
receives a license from the original licensors, to run, modify and
propagate that work, subject to this License.  You are not responsible
for enforcing compliance by third parties with this License.

  An "entity transaction" is a transaction transferring control of an
organization, or substantially all assets of one, or subdividing an
organization, or merging organizations.  If propagation of a covered
work results from an entity transaction, each party to that
transaction who receives a copy of the work also receives whatever
licenses to the work the party's predecessor in interest had or could
give under the previous paragraph, plus a right to possession of the
Corresponding Source of the work from the predecessor in interest, if
the predecessor has it or can get it with reasonable efforts.

  You may not impose any further restrictions on the exercise of the
rights granted or affirmed under this License.  For example, you may
not impose a license fee, royalty, or other charge for exercise of
rights granted under this License, and you may not initiate litigation
(including a cross-claim or counterclaim in a lawsuit) alleging that
any patent claim is infringed by making, using, selling, offering for
sale, or importing the Program or any portion of it.

  11. Patents.

  A "contributor" is a copyright holder who authorizes use under this
License of the Program or a work on which the Program is based.  The
work thus licensed is called the contributor's "contributor version".

  A contributor's "essential patent claims" are all patent claims
owned or controlled by the contributor, whether already acquired or
hereafter acquired, that would be infringed by some manner, permitted
by this License, of making, using, or selling its contributor version,
but do not include claims that would be infringed only as a
consequence of further modification of the contributor version.  For
purposes of this definition, "control" includes the right to grant
patent sublicenses in a manner consistent with the requirements of
this License.

  Each contributor grants you a non-exclusive, worldwide, royalty-free
patent license under the contributor's essential patent claims, to
make, use, sell, offer for sale, import and otherwise run, modify and
propagate the contents of its contributor version.

  In the following three paragraphs, a "patent license" is any express
agreement or commitment, however denominated, not to enforce a patent
(such as an express permission to practice a patent or covenant not to
sue for patent infringement).  To "grant" such a patent license to a
party means to make such an agreement or commitment not to enforce a
patent against the party.

  If you convey a covered work, knowingly relying on a patent license,
and the Corresponding Source of the work is not available for anyone
to copy, free of charge and under the terms of this License, through a
publicly available network server or other readily accessible means,
then you must either (1) cause the Corresponding Source to be so
available, or (2) arrange to deprive yourself of the benefit of the
patent license for this particular work, or (3) arrange, in a manner
consistent with the requirements of this License, to extend the patent
license to downstream recipients.  "Knowingly relying" means you have
actual knowledge that, but for the patent license, your conveying the
covered work in a country, or your recipient's use of the covered work
in a country, would infringe one or more identifiable patents in that
country that you have reason to believe are valid.

  If, pursuant to or in connection with a single transaction or
arrangement, you convey, or propagate by procuring conveyance of, a
covered work, and grant a patent license to some of the parties
receiving the covered work authorizing them to use, propagate, modify
or convey a specific copy of the covered work, then the patent license
you grant is automatically extended to all recipients of the covered
work and works based on it.

  A patent license is "discriminatory" if it does not include within
the scope of its coverage, prohibits the exercise of, or is
conditioned on the non-exercise of one or more of the rights that are
specifically granted under this License.  You may not convey a covered
work if you are a party to an arrangement with a third party that is
in the business of distributing software, under which you make payment
to the third party based on the extent of your activity of conveying
the work, and under which the third party grants, to any of the
parties who would receive the covered work from you, a discriminatory
patent license (a) in connection with copies of the covered work
conveyed by you (or copies made from those copies), or (b) primarily
for and in connection with specific products or compilations that
contain the covered work, unless you entered into that arrangement,
or that patent license was granted, prior to 28 March 2007.

  Nothing in this License shall be construed as excluding or limiting
any implied license or other defenses to infringement that may
otherwise be available to you under applicable patent law.

  12. No Surrender of Others' Freedom.

  If conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot convey a
covered work so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you may
not convey it at all.  For example, if you agree to terms that obligate you
to collect a royalty for further conveying from those to whom you convey
the Program, the only way you could satisfy both those terms and this
License would be to refrain entirely from conveying the Program.

  13. Use with the GNU Affero General Public License.

  Notwithstanding any other provision of this License, you have
permission to link or combine any covered work with a work licensed
under version 3 of the GNU Affero General Public License into a single
combined work, and to convey the resulting work.  The terms of this
License will continue to apply to the part which is the covered work,
but the special requirements of the GNU Affero General Public License,
section 13, concerning interaction through a network will apply to the
combination as such.

  14. Revised Versions of this License.

  The Free Software Foundation may publish revised and/or new versions of
the GNU General Public License from time to time.  Such new versions will
be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

  Each version is given a distinguishing version number.  If the
Program specifies that a certain numbered version of the GNU General
Public License "or any later version" applies to it, you have the
option of following the terms and conditions either of that numbered
version or of any later version published by the Free Software
Foundation.  If the Program does not specify a version number of the
GNU General Public License, you may choose any version ever published
by the Free Software Foundation.

  If the Program specifies that a proxy can decide which future
versions of the GNU General Public License can be used, that proxy's
public statement of acceptance of a version permanently authorizes you
to choose that version for the Program.

  Later license versions may give you additional or different
permissions.  However, no additional obligations are imposed on any
author or copyright holder as a result of your choosing to follow a
later version.

  15. Disclaimer of Warranty.

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  16. Limitation of Liability.

  IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGES.

  17. Interpretation of Sections 15 and 16.

  If the disclaimer of warranty and limitation of liability provided
above cannot be given local legal effect according to their terms,
reviewing courts shall apply local law that most closely approximates
an absolute waiver of all civil liability in connection with the
Program, unless a warranty or assumption of liability accompanies a
copy of the Program in return for a fee.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
state the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

  If the program does terminal interaction, make it output a short
notice like this when it starts in an interactive mode:

    <program>  Copyright (C) <year>  <name of author>
    This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
    This is free software, and you are welcome to redistribute it
    under certain conditions; type `show c' for details.

The hypothetical commands `show w' and `show c' should show the appropriate
parts of the General Public License.  Of course, your program's commands
might be different; for a GUI interface, you would use an "about box".

  You should also get your employer (if you work as a programmer) or school,
if any, to sign a "copyright disclaimer" for the program, if necessary.
For more information on this, and how to apply and follow the GNU GPL, see
<https://www.gnu.org/licenses/>.

  The GNU General Public License does not permit incorporating your program
into proprietary programs.  If your program is a subroutine library, you
may consider it more useful to permit linking proprietary applications with
the library.  If this is what you want to do, use the GNU Lesser General
Public License instead of this License.  But first, please read
<https://www.gnu.org/licenses/why-not-lgpl.html>.
````

## tools/bcpack_tables.py

SHA-256 `151d6434c4f915bc89a96af96f3bf6367048219c096ec2e444675fd961fd6336`

````python
"""Fixed codec constant tables for the clean-room BCPack decoder.

All values here are codec-level constants (rANS exponential probability models,
symbol-rank tables, and built-in initial endpoint history entries), not game
texture assets. Recovered clean-room from public specifications (US patent
11,234,023 and BCn block formats) and statistical/algebraic fitting; confirmed
and provisional built-in history entries are kept strictly separate so callers
can refuse unconfirmed entries by default.
"""

# (symbol_width, q) -> per-band rANS frequencies (band 0 is symbol 0;
# band p >= 1 covers symbols [2^(p-1), 2^p)); total weight is 65536.
PROB_TABLES = {
    (1, 0): (32768, 32768),
    (1, 1): (38761, 26775),
    (1, 2): (44484, 21052),
    (1, 3): (49818, 15718),
    (1, 4): (54623, 10913),
    (1, 5): (58721, 6815),
    (1, 6): (61911, 3625),
    (1, 7): (64036, 1500),
    (1, 8): (65121, 415),
    (1, 9): (65477, 59),
    (1, 10): (65534, 2),
    (1, 11): (65535, 1),
    (1, 12): (65535, 1),
    (1, 13): (65535, 1),
    (1, 14): (65535, 1),
    (1, 15): (65535, 1),
    (2, 0): (16384, 16384, 16384),
    (2, 1): (21168, 17592, 13388),
    (2, 2): (26354, 18130, 10526),
    (2, 3): (31900, 17918, 7859),
    (2, 4): (37750, 16874, 5456),
    (2, 5): (43800, 14920, 3408),
    (2, 6): (49850, 12062, 1812),
    (2, 7): (55537, 8499, 750),
    (2, 8): (60308, 4812, 208),
    (2, 9): (63575, 1901, 30),
    (2, 10): (65132, 402, 1),
    (2, 11): (65511, 23, 1),
    (2, 12): (65533, 1, 1),
    (2, 13): (65533, 1, 1),
    (2, 14): (65533, 1, 1),
    (2, 15): (65533, 1, 1),
    (3, 0): (8192, 8192, 8192, 8192),
    (3, 1): (11073, 10095, 8796, 6694),
    (3, 2): (14406, 11948, 9065, 5263),
    (3, 3): (18234, 13666, 8958, 3930),
    (3, 4): (22624, 15126, 8437, 2728),
    (3, 5): (27657, 16143, 7460, 1704),
    (3, 6): (33414, 16436, 6031, 906),
    (3, 7): (39920, 15616, 4250, 375),
    (3, 8): (47024, 13284, 2406, 104),
    (3, 9): (54201, 9375, 950, 15),
    (3, 10): (60388, 4744, 200, 1),
    (3, 11): (64250, 1262, 10, 1),
    (3, 12): (65456, 74, 1, 1),
    (3, 13): (65529, 1, 1, 1),
    (3, 14): (65529, 1, 1, 1),
    (3, 15): (65529, 1, 1, 1),
    (4, 0): (4096, 4096, 4096, 4096, 4096),
    (4, 1): (5665, 5407, 5048, 4398, 3347),
    (4, 2): (7539, 6867, 5973, 4532, 2632),
    (4, 3): (9773, 8461, 6833, 4479, 1965),
    (4, 4): (12447, 10177, 7564, 4218, 1364),
    (4, 5): (15679, 11977, 8072, 3730, 852),
    (4, 6): (19640, 13774, 8217, 3016, 453),
    (4, 7): (24559, 15361, 7808, 2124, 188),
    (4, 8): (30704, 16320, 6642, 1203, 52),
    (4, 9): (38280, 15920, 4688, 476, 7),
    (4, 10): (47169, 13219, 2372, 99, 1),
    (4, 11): (56354, 7896, 631, 4, 1),
    (4, 12): (63248, 2208, 34, 1, 1),
    (4, 13): (65465, 57, 1, 1, 1),
    (4, 14): (65521, 1, 1, 1, 1),
    (4, 15): (65521, 1, 1, 1, 1),
    (5, 0): (2048, 2048, 2048, 2048, 2048, 2048),
    (5, 1): (2865, 2799, 2704, 2524, 2200, 1673),
    (5, 2): (3858, 3682, 3434, 2986, 2266, 1316),
    (5, 3): (5063, 4709, 4230, 3418, 2240, 982),
    (5, 4): (6536, 5912, 5088, 3782, 2109, 682),
    (5, 5): (8366, 7314, 5988, 4036, 1865, 426),
    (5, 6): (10688, 8952, 6888, 4108, 1507, 227),
    (5, 7): (13713, 10847, 7680, 3904, 1062, 94),
    (5, 8): (17758, 12946, 8160, 3320, 602, 26),
    (5, 9): (23272, 15008, 7960, 2344, 237, 4),
    (5, 10): (30841, 16327, 6610, 1187, 48, 1),
    (5, 11): (41006, 15348, 3947, 316, 1, 1),
    (5, 12): (53291, 9957, 1104, 14, 1, 1),
    (5, 13): (63380, 2084, 22, 1, 1, 1),
    (5, 14): (65505, 1, 1, 1, 1, 1),
    (5, 15): (65505, 1, 1, 1, 1, 1),
    (6, 0): (1024, 1024, 1024, 1024, 1024, 1024, 1024),
    (6, 1): (1441, 1423, 1400, 1352, 1262, 1099, 837),
    (6, 2): (1951, 1907, 1841, 1717, 1493, 1133, 658),
    (6, 3): (2577, 2487, 2354, 2115, 1709, 1120, 491),
    (6, 4): (3350, 3186, 2956, 2544, 1890, 1055, 341),
    (6, 5): (4324, 4042, 3657, 2994, 2019, 932, 213),
    (6, 6): (5581, 5107, 4476, 3444, 2055, 754, 113),
    (6, 7): (7258, 6454, 5424, 3840, 1952, 531, 47),
    (6, 8): (9579, 8179, 6473, 4080, 1660, 301, 13),
    (6, 9): (12907, 10365, 7504, 3980, 1171, 119, 2),
    (6, 10): (17852, 12988, 8164, 3304, 594, 23, 1),
    (6, 11): (25441, 15565, 7673, 1974, 155, 1, 1),
    (6, 12): (37208, 16084, 4978, 552, 4, 1, 1),
    (6, 13): (53649, 9731, 1042, 4, 1, 1, 1),
    (6, 14): (65147, 327, 1, 1, 1, 1, 1),
    (6, 15): (65473, 1, 1, 1, 1, 1, 1),
    (7, 0): (512, 512, 512, 512, 512, 512, 512, 512),
    (7, 1): (722, 718, 712, 700, 676, 632, 550, 418),
    (7, 2): (981, 971, 952, 920, 858, 748, 566, 329),
    (7, 3): (1300, 1276, 1244, 1178, 1058, 854, 559, 246),
    (7, 4): (1696, 1654, 1593, 1478, 1272, 946, 526, 171),
    (7, 5): (2198, 2126, 2022, 1828, 1498, 1009, 467, 106),
    (7, 6): (2852, 2728, 2554, 2238, 1721, 1028, 376, 57),
    (7, 7): (3736, 3522, 3227, 2712, 1920, 977, 266, 23),
    (7, 8): (4979, 4601, 4090, 3236, 2040, 831, 151, 6),
    (7, 9): (6807, 6101, 5182, 3752, 1991, 586, 59, 1),
    (7, 10): (9634, 8218, 6494, 4082, 1652, 296, 11, 1),
    (7, 11): (14275, 11165, 7784, 3836, 988, 74, 1, 1),
    (7, 12): (22449, 14759, 8042, 2489, 272, 1, 1, 1),
    (7, 13): (37625, 16023, 4866, 509, 1, 1, 1, 1),
    (7, 14): (60485, 4663, 132, 1, 1, 1, 1, 1),
    (7, 15): (65409, 1, 1, 1, 1, 1, 1, 1),
    (8, 0): (256, 256, 256, 256, 256, 256, 256, 256, 256),
    (8, 1): (362, 360, 359, 356, 350, 338, 316, 275, 209),
    (8, 2): (492, 488, 486, 476, 460, 429, 374, 284, 164),
    (8, 3): (653, 647, 638, 622, 589, 529, 426, 280, 123),
    (8, 4): (853, 843, 828, 796, 739, 636, 473, 264, 85),
    (8, 5): (1108, 1090, 1063, 1011, 914, 748, 504, 234, 53),
    (8, 6): (1442, 1410, 1364, 1277, 1120, 860, 514, 189, 28),
    (8, 7): (1895, 1841, 1760, 1614, 1356, 961, 488, 132, 12),
    (8, 8): (2538, 2442, 2300, 2045, 1618, 1021, 414, 76, 3),
    (8, 9): (3497, 3311, 3050, 2591, 1875, 996, 292, 29, 1),
    (8, 10): (5008, 4626, 4109, 3247, 2041, 826, 149, 4, 1),
    (8, 11): (7575, 6701, 5582, 3892, 1918, 494, 34, 1, 1),
    (8, 12): (12397, 10051, 7380, 4020, 1245, 129, 1, 1, 1),
    (8, 13): (22767, 14857, 8012, 2432, 240, 1, 1, 1, 1),
    (8, 14): (47343, 13141, 2332, 35, 1, 1, 1, 1, 1),
    (8, 15): (65281, 1, 1, 1, 1, 1, 1, 1, 1),
    (9, 0): (128, 128, 128, 128, 128, 128, 128, 128, 128, 128),
    (9, 1): (181, 181, 179, 180, 178, 175, 169, 157, 137, 105),
    (9, 2): (246, 246, 244, 243, 238, 231, 214, 187, 142, 82),
    (9, 3): (327, 325, 324, 319, 310, 294, 265, 213, 141, 61),
    (9, 4): (428, 424, 422, 414, 397, 370, 319, 236, 131, 43),
    (9, 5): (557, 551, 546, 530, 506, 457, 374, 252, 116, 27),
    (9, 6): (725, 717, 705, 683, 638, 560, 430, 256, 95, 14),
    (9, 7): (955, 941, 920, 880, 807, 677, 481, 244, 66, 6),
    (9, 8): (1282, 1256, 1219, 1150, 1023, 810, 510, 207, 37, 2),
    (9, 9): (1772, 1724, 1656, 1524, 1295, 938, 498, 147, 13, 1),
    (9, 10): (2554, 2454, 2312, 2054, 1625, 1020, 414, 74, 1, 1),
    (9, 11): (3904, 3672, 3350, 2791, 1946, 959, 247, 14, 1, 1),
    (9, 12): (6523, 5873, 5026, 3690, 2011, 621, 58, 1, 1, 1),
    (9, 13): (12593, 10175, 7428, 4006, 1216, 105, 1, 1, 1, 1),
    (9, 14): (31009, 16335, 6572, 1136, 1, 1, 1, 1, 1, 1),
    (9, 15): (65025, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    (10, 0): (64, 64, 64, 64, 64, 64, 64, 64, 64, 64, 64),
    (10, 1): (91, 89, 90, 90, 90, 90, 88, 85, 79, 69, 52),
    (10, 2): (123, 123, 123, 123, 121, 120, 115, 108, 93, 71, 41),
    (10, 3): (164, 164, 162, 161, 160, 155, 148, 131, 108, 69, 31),
    (10, 4): (214, 214, 212, 211, 206, 199, 184, 160, 117, 67, 21),
    (10, 5): (279, 277, 276, 273, 265, 252, 229, 187, 126, 59, 13),
    (10, 6): (364, 360, 358, 352, 342, 319, 280, 215, 129, 47, 7),
    (10, 7): (479, 477, 470, 460, 441, 404, 339, 240, 122, 33, 3),
    (10, 8): (644, 638, 627, 610, 576, 511, 405, 254, 105, 18, 1),
    (10, 9): (892, 880, 862, 828, 763, 647, 469, 248, 73, 6, 1),
    (10, 10): (1290, 1264, 1227, 1156, 1028, 812, 510, 207, 34, 1, 1),
    (10, 11): (1982, 1922, 1836, 1674, 1396, 972, 481, 123, 4, 1, 1),
    (10, 12): (3347, 3177, 2936, 2513, 1846, 1004, 311, 22, 1, 1, 1),
    (10, 13): (6632, 5962, 5087, 3714, 2003, 609, 37, 1, 1, 1, 1),
    (10, 14): (17963, 13041, 8168, 3285, 506, 1, 1, 1, 1, 1, 1),
    (10, 15): (64513, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
}

# BC1 index lanes: symbol -> 2x2 quadrant byte (TL, TR, BL, BR in bits 0-1, 2-3, 4-5, 6-7).
BC1_QUADRANT = bytes([
    0xaa, 0xff, 0x00, 0x55, 0xfa, 0xaf, 0xfb, 0xbf, 0xfe, 0xef, 0xbb, 0xee, 0xdf, 0xba, 0x5a, 0xae,
    0x7f, 0xea, 0xab, 0xf7, 0xfd, 0xa5, 0x5f, 0xf5, 0xdd, 0x77, 0x66, 0x99, 0x2a, 0x8a, 0xa2, 0x50,
    0x05, 0xa8, 0x11, 0x9a, 0x44, 0x3f, 0xa6, 0xa9, 0xcf, 0xbe, 0xfc, 0xf3, 0x6a, 0xeb, 0x7e, 0xe7,
    0xdb, 0xbd, 0x7a, 0xa7, 0xda, 0x0f, 0xad, 0x57, 0xd5, 0x0a, 0x5d, 0x75, 0x2f, 0x6e, 0xf0, 0x8f,
    0xf8, 0xe6, 0x3d, 0xf2, 0xb9, 0x25, 0x7c, 0x9b, 0x3b, 0x85, 0xce, 0xec, 0x58, 0xb3, 0xd3, 0xa0,
    0x52, 0xde, 0x7b, 0x2b, 0xb7, 0x5e, 0xc7, 0xed, 0x5b, 0xb2, 0x8e, 0xcc, 0x6f, 0x19, 0xf6, 0x9f,
    0x64, 0xe8, 0xe5, 0x29, 0xf9, 0x33, 0x46, 0x22, 0xb5, 0xd7, 0x2d, 0x78, 0x56, 0x86, 0x88, 0x68,
    0x91, 0x95, 0x92, 0xd2, 0x87, 0x7d, 0x76, 0x67, 0x9d, 0x59, 0x65, 0xd9, 0x15, 0x37, 0x93, 0x5c,
    0xc6, 0x35, 0x6c, 0xcd, 0x39, 0x45, 0xdc, 0x54, 0x73, 0x51, 0x53, 0xc5, 0x2e, 0x8b, 0x8d, 0x27,
    0xe2, 0x1f, 0xf4, 0x1d, 0xd8, 0xf1, 0x72, 0xa3, 0x4f, 0x74, 0xb8, 0xca, 0x3a, 0xac, 0xd1, 0x89,
    0x47, 0x26, 0x62, 0x98, 0x70, 0x0d, 0xa1, 0x1a, 0x4a, 0x6b, 0x1b, 0xd0, 0xa4, 0xe9, 0x07, 0xb1,
    0x9e, 0xb6, 0xe4, 0x4e, 0xbc, 0xe3, 0x3e, 0xcb, 0x82, 0x31, 0x02, 0x28, 0x4c, 0x13, 0xc4, 0x20,
    0x0e, 0x0b, 0x08, 0x96, 0x80, 0xe0, 0x09, 0xb0, 0x69, 0x60, 0x06, 0x90, 0x23, 0x97, 0x8c, 0xd6,
    0x21, 0x6d, 0x79, 0x32, 0xc8, 0x48, 0x84, 0x17, 0x12, 0xd4, 0x4d, 0x71, 0x01, 0x36, 0x63, 0x9c,
    0xc9, 0x40, 0x04, 0x10, 0xe1, 0x16, 0x94, 0x49, 0x4b, 0x1e, 0xb4, 0x61, 0x03, 0x0c, 0xc0, 0x42,
    0x81, 0x18, 0x30, 0x24, 0xc3, 0x3c, 0xc2, 0x41, 0x14, 0x83, 0x2c, 0x38, 0x43, 0x34, 0x1c, 0xc1,
])

# BC1 built-in 256-entry endpoint history: index -> (r0, g0, b0, r1, g1, b1).
BC1_HISTORY_CONFIRMED = {
    1: (7, 29, 6, 8, 30, 7), 2: (15, 29, 15, 16, 36, 17), 3: (20, 38, 14, 3, 5, 2),
    4: (12, 27, 13, 6, 12, 6), 5: (10, 22, 11, 6, 14, 7), 7: (12, 26, 12, 7, 14, 7),
    8: (22, 36, 15, 20, 32, 14), 10: (23, 5, 30, 9, 5, 30), 11: (11, 22, 11, 7, 15, 7),
    12: (17, 22, 7, 10, 11, 3), 13: (12, 25, 12, 7, 16, 7), 14: (13, 28, 8, 5, 11, 3),
    15: (11, 20, 8, 16, 31, 14), 16: (23, 32, 30, 17, 12, 29), 17: (8, 44, 30, 6, 26, 30),
    18: (10, 24, 30, 6, 45, 30), 19: (10, 12, 4, 8, 8, 2), 20: (16, 23, 30, 14, 6, 26),
    21: (12, 25, 13, 10, 22, 12), 22: (19, 27, 10, 12, 15, 5), 23: (11, 24, 12, 4, 11, 6),
    24: (29, 60, 29, 6, 13, 6), 25: (17, 31, 11, 1, 2, 1), 26: (26, 54, 24, 12, 24, 10),
    27: (23, 49, 30, 20, 36, 30), 28: (16, 23, 10, 10, 14, 6), 29: (11, 24, 10, 6, 13, 5),
    30: (18, 52, 30, 14, 22, 30), 31: (14, 51, 30, 9, 34, 30), 32: (2, 3, 1, 19, 37, 16),
    33: (14, 15, 30, 9, 31, 30), 34: (29, 57, 27, 27, 52, 25), 35: (13, 29, 15, 8, 20, 11),
    36: (13, 17, 5, 9, 10, 3), 37: (18, 50, 29, 15, 10, 29), 38: (11, 25, 13, 8, 19, 10),
    39: (17, 32, 12, 6, 11, 4), 40: (22, 18, 30, 19, 41, 30), 41: (10, 22, 11, 8, 18, 9),
    42: (18, 30, 31, 10, 44, 30), 43: (25, 50, 24, 2, 4, 1), 44: (11, 30, 31, 7, 15, 29),
    45: (12, 19, 8, 11, 16, 7), 46: (19, 29, 30, 14, 55, 28), 47: (9, 20, 10, 4, 10, 5),
    48: (12, 24, 10, 7, 13, 5), 49: (26, 53, 25, 6, 13, 6), 50: (19, 27, 31, 11, 19, 30),
    51: (21, 31, 30, 22, 31, 30), 52: (10, 19, 5, 11, 21, 6), 53: (30, 50, 3, 29, 46, 2),
    54: (15, 9, 30, 7, 9, 30), 55: (14, 18, 6, 11, 14, 4), 56: (28, 56, 26, 4, 7, 3),
    57: (9, 20, 10, 5, 13, 7), 58: (28, 58, 26, 15, 32, 14), 59: (11, 19, 8, 6, 9, 4),
    60: (16, 22, 9, 13, 17, 7), 61: (1, 2, 1, 14, 28, 12), 62: (22, 45, 30, 9, 15, 30),
    63: (19, 22, 30, 16, 23, 31), 64: (25, 50, 24, 21, 43, 20), 65: (6, 11, 4, 16, 31, 13),
    66: (13, 25, 8, 3, 6, 1), 69: (20, 38, 16, 13, 25, 10), 70: (18, 35, 15, 5, 9, 3),
    72: (11, 21, 7, 7, 13, 4), 73: (20, 39, 16, 11, 20, 8), 75: (22, 41, 30, 18, 23, 30),
    76: (24, 50, 24, 9, 19, 8), 77: (3, 12, 7, 4, 16, 8), 78: (18, 27, 12, 16, 22, 10),
    79: (24, 49, 23, 13, 28, 12), 80: (24, 50, 24, 18, 37, 18), 81: (17, 33, 12, 14, 27, 9),
    82: (20, 10, 31, 13, 10, 31), 83: (7, 8, 2, 5, 5, 1), 84: (1, 2, 1, 10, 21, 9),
    85: (10, 18, 6, 1, 1, 0), 86: (22, 46, 21, 1, 3, 1), 87: (11, 20, 8, 8, 14, 5),
    88: (17, 35, 31, 14, 14, 29), 89: (16, 22, 31, 12, 40, 31), 90: (12, 22, 9, 8, 15, 6),
    91: (18, 15, 30, 15, 33, 31), 92: (19, 32, 30, 15, 43, 31), 93: (18, 35, 15, 8, 15, 5),
    94: (21, 43, 20, 18, 37, 17), 95: (10, 17, 6, 9, 15, 6), 96: (14, 27, 12, 7, 13, 5),
    97: (8, 16, 7, 12, 25, 11), 98: (18, 37, 17, 1, 1, 0), 99: (17, 45, 30, 15, 33, 31),
    100: (13, 25, 11, 8, 16, 7), 101: (23, 47, 22, 16, 32, 15), 102: (18, 33, 13, 11, 21, 8),
    103: (4, 10, 4, 8, 17, 7), 104: (1, 2, 1, 3, 7, 3), 105: (11, 22, 9, 6, 11, 4),
    106: (16, 29, 11, 13, 23, 9), 107: (12, 24, 12, 6, 12, 6), 108: (23, 47, 22, 7, 14, 6),
    109: (11, 32, 30, 11, 31, 30), 110: (14, 26, 11, 10, 18, 7), 111: (20, 41, 19, 1, 3, 1),
    112: (14, 28, 12, 8, 16, 6), 113: (11, 21, 9, 8, 15, 6), 114: (1, 2, 1, 7, 13, 6),
    115: (19, 35, 14, 16, 29, 12), 116: (13, 27, 13, 7, 15, 7), 117: (15, 33, 16, 8, 18, 9),
    118: (15, 42, 31, 11, 22, 30), 119: (23, 48, 23, 4, 9, 4), 120: (22, 45, 21, 11, 22, 10),
    121: (31, 62, 30, 31, 61, 29), 123: (19, 39, 19, 9, 20, 10), 124: (7, 14, 2, 6, 12, 2),
    125: (21, 42, 20, 3, 7, 3), 126: (10, 17, 7, 8, 13, 5), 127: (11, 20, 8, 9, 17, 7),
    128: (19, 33, 31, 12, 31, 31), 129: (21, 43, 20, 5, 11, 5), 130: (10, 20, 9, 7, 13, 6),
    131: (10, 21, 10, 6, 13, 6), 132: (15, 29, 12, 11, 20, 8), 133: (21, 43, 20, 9, 18, 8),
    134: (3, 8, 3, 5, 11, 5), 135: (16, 31, 13, 9, 17, 7), 136: (11, 22, 11, 6, 12, 6),
    137: (10, 21, 10, 7, 15, 7), 138: (27, 3, 1, 26, 1, 0), 139: (18, 37, 18, 16, 32, 16),
    140: (12, 23, 10, 9, 17, 7), 141: (12, 25, 12, 8, 17, 8), 142: (11, 21, 9, 2, 4, 1),
    143: (7, 15, 7, 8, 18, 9), 144: (17, 33, 15, 13, 24, 11), 145: (9, 19, 9, 7, 15, 7),
    146: (21, 43, 20, 13, 27, 12), 147: (17, 36, 17, 2, 4, 2), 148: (10, 20, 9, 6, 12, 5),
    149: (20, 41, 19, 7, 14, 7), 150: (3, 9, 6, 2, 8, 5), 151: (13, 24, 10, 11, 20, 8),
    152: (18, 38, 18, 4, 7, 3), 153: (19, 38, 18, 8, 17, 8), 154: (16, 35, 17, 4, 10, 4),
    155: (11, 23, 11, 10, 21, 10), 156: (17, 36, 17, 7, 14, 7), 157: (13, 27, 13, 6, 12, 6),
    158: (9, 15, 4, 8, 13, 4), 159: (10, 19, 7, 5, 9, 3), 160: (19, 40, 19, 11, 24, 11),
    161: (11, 23, 11, 8, 17, 8), 162: (14, 29, 14, 7, 15, 7), 163: (12, 22, 9, 5, 8, 3),
    164: (10, 20, 9, 8, 17, 8), 165: (21, 42, 19, 15, 31, 14), 166: (14, 29, 13, 1, 1, 0),
    167: (8, 16, 8, 7, 14, 7), 168: (9, 18, 8, 8, 16, 7), 169: (10, 17, 7, 3, 4, 1),
    170: (14, 28, 13, 2, 4, 1), 171: (14, 30, 14, 3, 6, 3), 172: (19, 38, 18, 5, 11, 5),
    173: (12, 26, 12, 1, 2, 1), 174: (9, 16, 6, 8, 13, 5), 175: (8, 13, 4, 7, 11, 4),
    176: (16, 34, 16, 3, 7, 3), 177: (13, 28, 13, 4, 9, 4), 178: (15, 31, 15, 6, 13, 6),
    179: (12, 24, 11, 9, 19, 9), 180: (9, 19, 8, 7, 14, 6), 181: (14, 28, 13, 5, 10, 4),
    182: (10, 20, 7, 4, 6, 2), 183: (16, 34, 17, 11, 25, 12), 184: (15, 30, 15, 8, 16, 8),
    185: (13, 27, 13, 10, 20, 10), 186: (9, 20, 9, 0, 1, 0), 187: (16, 32, 15, 2, 4, 2),
    188: (13, 27, 12, 3, 6, 3), 189: (13, 26, 12, 12, 23, 11), 190: (12, 25, 12, 5, 10, 5),
    191: (11, 23, 11, 5, 11, 5), 192: (16, 34, 16, 6, 12, 5), 193: (16, 35, 31, 15, 25, 31),
    194: (16, 33, 16, 7, 15, 7), 195: (13, 27, 13, 8, 18, 8), 196: (18, 36, 17, 11, 22, 10),
    197: (18, 37, 18, 13, 27, 13), 198: (12, 25, 12, 4, 8, 4), 199: (9, 18, 7, 6, 11, 4),
    200: (15, 30, 14, 9, 19, 9), 201: (17, 35, 16, 9, 18, 9), 202: (11, 24, 11, 2, 4, 2),
    203: (16, 33, 16, 0, 1, 0), 204: (15, 31, 15, 4, 9, 4), 205: (16, 31, 15, 14, 27, 13),
    206: (14, 29, 14, 13, 25, 12), 207: (11, 23, 11, 3, 6, 3), 208: (16, 32, 16, 10, 21, 10),
    209: (11, 22, 11, 4, 9, 4), 210: (11, 22, 10, 1, 2, 0), 211: (8, 14, 5, 2, 4, 1),
    212: (9, 16, 6, 6, 10, 4), 213: (10, 21, 10, 9, 19, 9), 214: (14, 30, 14, 11, 22, 11),
    215: (9, 18, 8, 6, 13, 6), 216: (6, 13, 6, 5, 11, 5), 217: (7, 14, 6, 0, 1, 0),
    218: (4, 7, 2, 3, 4, 1), 219: (10, 20, 9, 4, 8, 4), 220: (9, 17, 7, 5, 9, 3),
    221: (7, 14, 7, 1, 2, 1), 222: (10, 20, 10, 5, 10, 5), 223: (8, 15, 5, 4, 6, 2),
    224: (8, 17, 8, 1, 2, 1), 225: (10, 20, 10, 3, 6, 3), 226: (7, 10, 3, 6, 8, 3),
    227: (8, 15, 7, 6, 12, 6), 228: (9, 19, 9, 2, 4, 2), 229: (6, 11, 4, 3, 4, 1),
    230: (6, 11, 4, 0, 1, 0), 231: (8, 16, 7, 2, 4, 2), 232: (16, 34, 16, 15, 29, 15),
    233: (7, 16, 7, 5, 10, 5), 234: (8, 14, 5, 5, 9, 3), 235: (9, 18, 8, 4, 8, 4),
    236: (5, 9, 3, 4, 7, 2), 237: (9, 18, 8, 5, 10, 5), 238: (6, 12, 6, 2, 4, 2),
    239: (7, 12, 5, 4, 7, 3), 240: (5, 11, 5, 1, 2, 1), 241: (8, 17, 8, 3, 6, 3),
    242: (16, 31, 31, 16, 32, 31), 243: (7, 14, 7, 3, 6, 3), 244: (5, 11, 6, 4, 9, 4),
    245: (7, 15, 7, 4, 8, 4), 246: (2, 4, 2, 0, 0, 1), 247: (5, 11, 5, 3, 6, 3),
    248: (4, 8, 4, 1, 1, 1), 249: (3, 6, 3, 1, 2, 1), 250: (2, 4, 1, 1, 2, 1),
    251: (4, 8, 4, 3, 6, 3), 252: (3, 6, 3, 2, 4, 2), 253: (4, 9, 4, 2, 4, 2),
    254: (17, 27, 31, 15, 34, 31), 255: (0, 0, 1, 0, 0, 0),
}

BC1_HISTORY_PROVISIONAL = {
    6: (12, 24, 11, 7, 14, 6), 9: (14, 23, 8, 1, 2, 1), 67: (5, 9, 3, 12, 24, 10),
    68: (16, 29, 13, 7, 13, 5), 71: (13, 25, 11, 6, 11, 4), 74: (16, 31, 12, 4, 8, 2),
    122: (13, 26, 11, 5, 8, 3),
}

# BC3 3-bit alpha index pair rank table (64 entries) and colour quadrant rank table (256 entries).
BC3_ALPHA_PAIR = (
    (0, 0), (1, 1), (6, 6), (4, 4), (3, 3), (5, 5), (7, 7), (1, 6),
    (6, 1), (0, 1), (1, 0), (7, 1), (1, 7), (0, 3), (3, 0), (0, 2),
    (2, 0), (2, 2), (5, 4), (3, 4), (4, 3), (4, 5), (1, 5), (5, 1),
    (0, 4), (4, 0), (2, 3), (3, 2), (5, 3), (3, 5), (6, 5), (5, 6),
    (6, 7), (7, 6), (5, 7), (4, 6), (6, 4), (7, 5), (6, 0), (0, 6),
    (4, 2), (2, 4), (4, 1), (1, 4), (5, 0), (0, 5), (6, 3), (3, 6),
    (3, 1), (5, 2), (1, 3), (2, 5), (7, 4), (4, 7), (7, 3), (3, 7),
    (2, 6), (6, 2), (2, 1), (1, 2), (0, 7), (7, 0), (2, 7), (7, 2),
)

BC3_COLOUR_QUADRANT = bytes([
    0x55, 0xaa, 0xff, 0x00, 0x50, 0x05, 0xaf, 0xfa, 0xae, 0xea, 0xab, 0xba, 0xee, 0xbb, 0xfe, 0xbf,
    0xef, 0xfb, 0xa5, 0x5a, 0xf0, 0x11, 0x0f, 0x44, 0xf5, 0x5f, 0xa0, 0x0a, 0x8a, 0xa2, 0xa8, 0x2a,
    0x7f, 0xf7, 0x77, 0xdf, 0xfd, 0xdd, 0x66, 0x99, 0x88, 0xbe, 0xeb, 0x22, 0xcc, 0x33, 0x8f, 0xf8,
    0x57, 0x75, 0xd5, 0x5d, 0x2f, 0xf2, 0x7a, 0x85, 0xa7, 0xda, 0x58, 0x25, 0xad, 0x52, 0x3f, 0xf3,
    0xcf, 0xe8, 0xfc, 0x8e, 0x2b, 0x7e, 0x6a, 0xa6, 0x9a, 0x70, 0x07, 0x0d, 0xa9, 0x78, 0x80, 0x08,
    0x02, 0xe7, 0xb2, 0x20, 0xdb, 0xd0, 0x87, 0x5e, 0xbd, 0x7c, 0x2d, 0xe5, 0xc7, 0xec, 0xce, 0x5b,
    0xb3, 0xd2, 0x2e, 0xb5, 0x3b, 0xe0, 0xe6, 0x6e, 0x68, 0x8b, 0x9b, 0xe2, 0xb9, 0x0e, 0xb8, 0x0b,
    0x3d, 0xd3, 0x51, 0x86, 0x27, 0x45, 0x15, 0xde, 0x54, 0x8d, 0xb7, 0xed, 0x7b, 0xb0, 0xd8, 0x29,
    0x72, 0x92, 0x7d, 0xd7, 0x35, 0xa3, 0xc5, 0x82, 0x37, 0x53, 0x28, 0x5c, 0x56, 0x65, 0x76, 0x95,
    0x59, 0xcd, 0x9f, 0x3a, 0x73, 0x89, 0xca, 0xac, 0x67, 0x9d, 0xf6, 0xd9, 0xf9, 0x91, 0x19, 0xdc,
    0x98, 0x6c, 0x46, 0x64, 0x6f, 0x26, 0x39, 0x62, 0xc6, 0x93, 0x09, 0x23, 0x06, 0x60, 0x8c, 0xc8,
    0x90, 0x32, 0x03, 0x3e, 0xc0, 0x13, 0x31, 0xe3, 0x4c, 0x9e, 0x0c, 0xc4, 0xcb, 0xbc, 0xb6, 0xe9,
    0x30, 0x6b, 0x1f, 0xf1, 0x1d, 0xd1, 0x47, 0x74, 0x4f, 0x10, 0x40, 0xf4, 0x01, 0x04, 0xa1, 0x1a,
    0xa4, 0x1b, 0x4a, 0xb1, 0xe4, 0x4e, 0x36, 0xc9, 0x9c, 0x63, 0x97, 0x71, 0x79, 0x17, 0x48, 0x69,
    0x21, 0x12, 0x3c, 0x84, 0x83, 0x6d, 0xd6, 0x96, 0xc3, 0x38, 0x1e, 0x4d, 0xe1, 0xd4, 0xc2, 0x2c,
    0x18, 0x81, 0xb4, 0x4b, 0x16, 0x61, 0xc1, 0x24, 0x1c, 0x49, 0x14, 0x42, 0x94, 0x41, 0x34, 0x43,
])

# BC3 built-in endpoint history: index -> (a0, a1, r0, g0, b0, r1, g1, b1).
BC3_HISTORY_CONFIRMED = {}

BC3_HISTORY_PROVISIONAL = {
    2: (177, 134, 27, 55, 24, 14, 54, 24), 26: (255, 255, 21, 34, 8, 15, 22, 3),
    29: (220, 109, 17, 35, 17, 15, 30, 15), 30: (219, 96, 2, 53, 14, 2, 59, 16),
    35: (95, 65, 16, 31, 16, 15, 31, 15), 37: (136, 13, 16, 33, 16, 15, 32, 15),
    47: (146, 108, 18, 37, 18, 13, 26, 13), 52: (255, 255, 20, 38, 16, 3, 5, 2),
    71: (200, 51, 17, 34, 17, 15, 31, 15), 76: (170, 150, 2, 60, 20, 1, 61, 20),
    78: (248, 10, 3, 4, 2, 0, 1, 0), 95: (237, 229, 26, 51, 25, 1, 3, 1),
    98: (255, 0, 19, 38, 18, 14, 29, 13), 104: (255, 6, 13, 27, 13, 8, 17, 8),
    109: (254, 4, 15, 27, 11, 3, 4, 2), 112: (117, 39, 21, 41, 21, 1, 3, 1),
    126: (170, 119, 16, 31, 16, 15, 30, 15), 138: (122, 121, 14, 29, 14, 13, 27, 13),
    139: (247, 1, 15, 28, 13, 9, 16, 7), 153: (105, 126, 2, 7, 4, 1, 3, 2),
    154: (93, 100, 20, 40, 20, 15, 30, 15), 166: (91, 99, 17, 35, 17, 15, 30, 15),
    167: (155, 99, 16, 33, 16, 15, 31, 15), 177: (255, 255, 13, 24, 12, 11, 23, 10),
    185: (254, 255, 10, 17, 7, 2, 3, 1), 197: (253, 255, 11, 20, 9, 6, 11, 4),
    210: (254, 255, 5, 10, 5, 1, 2, 1), 220: (255, 255, 11, 20, 9, 9, 18, 7),
    225: (106, 113, 24, 39, 23, 0, 13, 0), 226: (1, 255, 8, 15, 7, 5, 10, 4),
    230: (1, 2, 0, 1, 1, 0, 0, 0), 232: (140, 131, 16, 31, 16, 15, 34, 16),
    237: (255, 254, 5, 11, 5, 4, 9, 3), 244: (255, 255, 1, 1, 1, 0, 0, 0),
    246: (253, 254, 3, 5, 2, 1, 2, 1),
}

# BC4 3-bit index pair rank table (64 entries) and built-in endpoint history: index -> (a0, a1).
BC4_PAIR = (
    (1, 1), (0, 0), (3, 3), (6, 6), (4, 4), (5, 5), (3, 0), (0, 3),
    (6, 1), (1, 6), (7, 7), (2, 2), (6, 3), (3, 6), (1, 0), (0, 1),
    (4, 1), (1, 4), (3, 1), (1, 3), (6, 0), (0, 6), (4, 2), (7, 5),
    (5, 7), (2, 4), (0, 5), (5, 0), (6, 4), (4, 6), (5, 3), (3, 5),
    (4, 0), (0, 4), (1, 5), (5, 1), (3, 4), (4, 3), (2, 6), (6, 2),
    (7, 3), (3, 7), (1, 2), (2, 1), (0, 7), (7, 0), (2, 5), (5, 2),
    (7, 4), (4, 7), (4, 5), (5, 4), (3, 2), (2, 3), (0, 2), (2, 0),
    (1, 7), (7, 1), (6, 5), (5, 6), (6, 7), (7, 6), (2, 7), (7, 2),
)

BC4_HISTORY_CONFIRMED = {}

BC4_HISTORY_PROVISIONAL = {
    25: (81, 50), 33: (58, 31), 77: (164, 124), 84: (204, 140),
    93: (208, 61), 101: (171, 137), 102: (212, 125), 116: (77, 34),
    119: (193, 127), 121: (178, 118), 126: (138, 108), 127: (132, 115),
    131: (165, 52), 142: (142, 80), 145: (74, 16), 148: (150, 124),
    154: (195, 103), 157: (71, 51), 163: (55, 33), 172: (139, 119),
    173: (42, 15), 178: (91, 47), 179: (48, 8), 184: (72, 34),
    185: (158, 136), 187: (105, 12), 188: (142, 38), 190: (43, 25),
    197: (133, 133), 200: (55, 17), 202: (82, 43), 207: (127, 129),
    208: (39, 9), 209: (134, 27), 211: (39, 23), 213: (19, 41),
    214: (39, 17), 217: (115, 21), 218: (118, 60), 221: (47, 17),
    223: (64, 25), 224: (119, 33), 227: (33, 16), 232: (78, 5),
    234: (33, 60), 235: (57, 24), 236: (69, 2), 239: (105, 24),
    240: (96, 34), 241: (111, 44), 243: (47, 25), 244: (84, 23),
    247: (22, 17), 252: (27, 8), 254: (12, 6),
}

# BC5 3-bit index pair rank table (64 entries) and built-in endpoint history: index -> (r0, r1, g0, g1).
BC5_PAIR = (
    (0, 0), (1, 1), (4, 4), (3, 3), (6, 6), (7, 7), (4, 0), (0, 4),
    (0, 1), (2, 2), (1, 0), (3, 0), (0, 3), (5, 5), (2, 0), (0, 2),
    (1, 6), (6, 1), (4, 3), (1, 7), (3, 4), (1, 4), (7, 1), (6, 0),
    (0, 6), (6, 3), (6, 4), (3, 6), (3, 2), (4, 6), (1, 5), (1, 3),
    (2, 3), (5, 4), (5, 3), (5, 0), (4, 1), (7, 6), (4, 5), (4, 2),
    (3, 1), (3, 5), (5, 1), (6, 7), (2, 4), (7, 5), (7, 4), (0, 5),
    (6, 5), (4, 7), (5, 7), (7, 0), (5, 6), (0, 7), (7, 3), (3, 7),
    (5, 2), (2, 5), (1, 2), (6, 2), (2, 1), (2, 6), (7, 2), (2, 7),
)

BC5_HISTORY_CONFIRMED = {
    182: (133, 126, 124, 55), 183: (128, 126, 116, 112), 222: (131, 128, 123, 37),
}

BC5_HISTORY_PROVISIONAL = {
    3: (130, 218, 45, 192), 4: (172, 109, 158, 94), 5: (183, 136, 113, 69),
    6: (125, 129, 86, 34), 7: (171, 196, 33, 82), 9: (142, 149, 102, 118),
    14: (82, 62, 26, 23), 15: (100, 94, 32, 32), 16: (97, 123, 61, 97),
    19: (133, 140, 118, 123), 20: (206, 194, 128, 123), 22: (147, 145, 64, 66),
    24: (76, 189, 55, 171), 27: (94, 115, 86, 102), 28: (163, 38, 152, 29),
    29: (143, 133, 89, 80), 30: (197, 67, 172, 50), 31: (164, 218, 130, 127),
    32: (141, 145, 111, 132), 33: (177, 125, 131, 32), 34: (49, 113, 26, 94),
    36: (173, 169, 40, 28), 38: (117, 125, 43, 50), 39: (139, 111, 99, 72),
    40: (123, 93, 83, 49), 41: (189, 166, 135, 116), 42: (198, 97, 178, 73),
    43: (205, 201, 76, 86), 44: (172, 174, 73, 72), 46: (157, 210, 136, 188),
    47: (126, 149, 115, 129), 48: (158, 67, 137, 41), 49: (214, 120, 131, 80),
    51: (147, 150, 119, 119), 52: (169, 107, 135, 65), 54: (231, 168, 223, 154),
    55: (115, 144, 99, 120), 56: (74, 104, 50, 83), 57: (220, 132, 32, 123),
    58: (150, 136, 110, 96), 60: (139, 147, 124, 108), 61: (121, 124, 78, 94),
    63: (169, 151, 124, 103), 64: (120, 106, 103, 88), 65: (134, 147, 110, 109),
    67: (133, 125, 103, 107), 68: (160, 133, 118, 123), 69: (175, 78, 163, 68),
    70: (229, 133, 166, 121), 71: (233, 147, 224, 134), 72: (127, 142, 104, 121),
    73: (134, 150, 99, 121), 74: (110, 149, 83, 129), 75: (175, 187, 129, 141),
    77: (115, 124, 96, 104), 78: (164, 128, 141, 109), 79: (129, 85, 114, 22),
    80: (246, 131, 241, 125), 82: (168, 186, 145, 165), 83: (192, 133, 158, 100),
    84: (107, 143, 105, 133), 85: (201, 212, 172, 181), 86: (124, 138, 116, 121),
    87: (92, 60, 71, 40), 88: (203, 134, 149, 126), 90: (61, 123, 25, 114),
    91: (123, 160, 113, 145), 92: (150, 169, 135, 150), 93: (134, 139, 101, 109),
    94: (253, 94, 255, 63), 95: (123, 87, 106, 67), 96: (238, 133, 121, 121),
    98: (24, 18, 15, 10), 99: (117, 41, 97, 25), 100: (123, 121, 70, 67),
    101: (64, 59, 51, 49), 102: (11, 103, 12, 88), 103: (144, 133, 111, 123),
    104: (189, 200, 65, 52), 105: (219, 153, 195, 135), 106: (150, 110, 138, 98),
    107: (118, 142, 60, 117), 108: (139, 145, 114, 118), 109: (216, 225, 191, 200),
    110: (46, 46, 38, 33), 111: (91, 132, 85, 126), 112: (154, 178, 115, 132),
    114: (131, 127, 125, 17), 115: (136, 134, 15, 123), 116: (131, 129, 105, 123),
    119: (132, 215, 122, 149), 120: (129, 138, 112, 111), 123: (136, 145, 119, 131),
    124: (179, 196, 165, 183), 125: (126, 125, 111, 92), 126: (136, 150, 122, 123),
    127: (168, 158, 136, 126), 128: (146, 153, 129, 134), 129: (127, 130, 85, 124),
    130: (132, 241, 120, 126), 131: (155, 124, 125, 85), 132: (121, 115, 115, 108),
    133: (106, 72, 89, 51), 134: (136, 155, 118, 137), 135: (121, 145, 106, 133),
    136: (119, 220, 102, 209), 137: (179, 136, 150, 122), 138: (120, 133, 102, 113),
    139: (145, 142, 111, 112), 140: (130, 108, 123, 62), 141: (121, 132, 37, 122),
    142: (157, 142, 135, 119), 143: (80, 201, 59, 191), 144: (130, 133, 122, 104),
    145: (138, 136, 112, 120), 146: (131, 107, 123, 37), 147: (122, 120, 107, 119),
    148: (126, 181, 121, 146), 149: (143, 141, 137, 135), 150: (134, 178, 121, 161),
    151: (103, 135, 55, 126), 152: (193, 132, 128, 123), 153: (141, 129, 111, 114),
    154: (79, 77, 53, 51), 155: (133, 72, 127, 64), 157: (102, 101, 83, 80),
    159: (92, 137, 39, 125), 160: (108, 136, 87, 122), 161: (102, 97, 65, 57),
    162: (163, 149, 151, 134), 163: (133, 17, 121, 15), 165: (179, 162, 153, 133),
    166: (119, 132, 98, 125), 167: (175, 132, 130, 124), 169: (132, 92, 124, 81),
    170: (40, 31, 27, 19), 171: (188, 211, 180, 202), 172: (139, 121, 117, 101),
    173: (150, 125, 130, 106), 174: (129, 184, 123, 131), 175: (132, 158, 126, 148),
    176: (130, 155, 126, 129), 177: (131, 167, 124, 127), 178: (155, 131, 132, 125),
    179: (198, 139, 170, 124), 180: (200, 196, 190, 186), 184: (173, 157, 163, 147),
    185: (197, 175, 158, 137), 186: (102, 129, 98, 126), 187: (131, 216, 121, 198),
    188: (127, 135, 115, 130), 189: (139, 196, 94, 111), 190: (132, 106, 123, 94),
    191: (219, 130, 193, 116), 192: (212, 133, 127, 124), 193: (196, 176, 173, 151),
    194: (56, 192, 15, 27), 195: (129, 198, 124, 131), 196: (131, 124, 125, 99),
    197: (176, 130, 169, 126), 198: (137, 127, 121, 111), 199: (144, 137, 131, 123),
    200: (132, 130, 114, 120), 201: (182, 165, 169, 153), 202: (138, 136, 113, 109),
    203: (185, 172, 179, 164), 204: (131, 127, 123, 81), 205: (124, 141, 121, 137),
    206: (173, 131, 136, 92), 208: (120, 133, 108, 123), 209: (147, 134, 123, 110),
    210: (130, 142, 125, 129), 211: (136, 137, 122, 131), 212: (130, 119, 127, 114),
    214: (117, 136, 111, 131), 215: (199, 181, 187, 167), 216: (132, 215, 124, 125),
    217: (135, 138, 120, 114), 218: (131, 85, 123, 45), 219: (197, 131, 193, 126),
    221: (69, 206, 57, 195), 223: (161, 156, 96, 92), 225: (130, 136, 123, 121),
    226: (126, 60, 118, 46), 227: (139, 137, 120, 124), 228: (140, 130, 124, 123),
    229: (122, 127, 118, 123), 231: (130, 141, 127, 138), 232: (54, 205, 50, 185),
    233: (75, 74, 69, 68), 234: (223, 130, 217, 125), 235: (111, 129, 108, 127),
    236: (160, 129, 157, 126), 237: (129, 217, 126, 217), 238: (148, 128, 146, 126),
    239: (130, 129, 127, 118), 241: (60, 200, 50, 200), 242: (131, 130, 120, 124),
    243: (123, 132, 116, 127), 244: (132, 135, 130, 132), 245: (129, 41, 126, 37),
    246: (122, 133, 120, 133), 247: (118, 128, 116, 126), 248: (136, 128, 133, 126),
    249: (128, 133, 123, 131), 250: (82, 81, 78, 77), 251: (124, 130, 122, 128),
    252: (130, 130, 125, 124), 253: (128, 128, 127, 127), 254: (127, 126, 126, 125),
    255: (129, 127, 128, 126),
}
````

## tools/bcpack_tables_bptc.py

SHA-256 `dc181b825d41c0f58e4eb79809061f4f99e81a9d462055d27ffd159a82525ffd`

````python
"""Public BPTC (BC6H and BC7) specification tables and runtime history loader.

Everything embedded in this module is either standard public D3D11 / Khronos
BPTC specification data (2-subset and 3-subset partition masks and anchor pixel
indices) or the BC7 lane-15 bitstream signature permutation (`BC7_CONFIG`).

BCPack's 256-entry initial endpoint/index history buffers for BC6H and BC7 are
**not** embedded in this repository because they are unpublished codec
constants that can only be recovered locally from the player's own texture
pools. Callers can decode self-contained BC6H/BC7 chunks (delta chains that
stay within the chunk) with `history=None`, or pass a locally generated JSON
file or directory (`--history <path>`) at runtime.
"""
import json
import os

# Standard D3D11 / Khronos BPTC 2-subset (64 x 16 pixels, 1 bit/pixel) and
# 3-subset (64 x 16 pixels, 2 bits/pixel) partition masks.
_BC7_PART2_PACKED = (
    0xcccc, 0x8888, 0xeeee, 0xecc8, 0xc880, 0xfeec, 0xfec8, 0xec80,
    0xc800, 0xffec, 0xfe80, 0xe800, 0xffe8, 0xff00, 0xfff0, 0xf000,
    0xf710, 0x008e, 0x7100, 0x08ce, 0x008c, 0x7310, 0x3100, 0x8cce,
    0x088c, 0x3110, 0x6666, 0x366c, 0x17e8, 0x0ff0, 0x718e, 0x399c,
    0xaaaa, 0xf0f0, 0x5a5a, 0x33cc, 0x3c3c, 0x55aa, 0x9696, 0xa55a,
    0x73ce, 0x13c8, 0x324c, 0x3bdc, 0x6996, 0xc33c, 0x9966, 0x0660,
    0x0272, 0x04e4, 0x4e40, 0x2720, 0xc936, 0x936c, 0x39c6, 0x639c,
    0x9336, 0x9cc6, 0x817e, 0xe718, 0xccf0, 0x0fcc, 0x7744, 0xee22,
)

_BC7_PART3_PACKED = (
    0xaa685050, 0x6a5a5040, 0x5a5a4200, 0x5450a0a8, 0xa5a50000, 0xa0a05050,
    0x5555a0a0, 0x5a5a5050, 0xaa550000, 0xaa555500, 0xaaaa5500, 0x90909090,
    0x94949494, 0xa4a4a4a4, 0xa9a59450, 0x2a0a4250, 0xa5945040, 0x0a425054,
    0xa5a5a500, 0x55a0a0a0, 0xa8a85454, 0x6a6a4040, 0xa4a45000, 0x1a1a0500,
    0x0050a4a4, 0xaaa59090, 0x14696914, 0x69691400, 0xa08585a0, 0xaa821414,
    0x50a4a450, 0x6a5a0200, 0xa9a58000, 0x5090a0a8, 0xa8a09050, 0x24242424,
    0x00aa5500, 0x24924924, 0x24499224, 0x50a50a50, 0x500aa550, 0xaaaa4444,
    0x66660000, 0xa5a0a5a0, 0x50a050a0, 0x69286928, 0x44aaaa44, 0x66666600,
    0xaa444444, 0x54a854a8, 0x95809580, 0x96969600, 0xa85454a8, 0x80959580,
    0xaa141414, 0x96960000, 0xaaaa1414, 0xa05050a0, 0xa0a5a5a0, 0x96000000,
    0x40804080, 0xa9a8a9a8, 0xaaaaaa44, 0x2a4a5254,
)

# Second and third subset anchor pixel indices (subset 0 anchor is always 0).
# BC6H two-region partitions use the first 32 entries of BC7_ANCHOR2.
BC7_ANCHOR2 = (
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
    15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6,
    6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15,
)

BC7_ANCHOR3A = (
    3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3,
    3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
    8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15,
    3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3,
)

BC7_ANCHOR3B = (
    15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8,
    15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
    15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8,
    15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8,
)

# BC7 lane-15 signature rank -> (mode, partition, rotation, index_selection).
# Lane-15 symbol pairs (a, b) on the 32 x 16 grid are ranked by
# `((a + 1) * (b + 1), a)` ascending. Modes 7, 6, 5, 4, 3 and 1 follow exact
# descending formulas; the 22 mode-2 partitions placed before mode 1 and the
# remaining 42 placed after mode 0 are both descending subsets of 0..63.
_BC7_MODE2_HEAD = (
    63, 59, 58, 57, 54, 53, 52, 47, 43, 42, 40,
    38, 37, 35, 34, 32, 23, 21, 18, 17, 16, 11,
)


def _build_bc7_config():
    head_set = set(_BC7_MODE2_HEAD)
    mode2_tail = tuple(p for p in range(63, -1, -1) if p not in head_set)
    return (
        tuple((7, 63 - r, 0, 0) for r in range(64))
        + ((6, 0, 0, 0),)
        + tuple((5, 0, 3 - r, 0) for r in range(4))
        + tuple((4, 0, (7 - r) >> 1, (7 - r) & 1) for r in range(8))
        + tuple((3, 63 - r, 0, 0) for r in range(64))
        + tuple((2, p, 0, 0) for p in _BC7_MODE2_HEAD)
        + tuple((1, 63 - r, 0, 0) for r in range(64))
        + tuple((0, p, 0, 0) for p in (*range(15, 7, -1), *range(5, -1, -1)))
        + tuple((2, p, 0, 0) for p in mode2_tail)
        + ((0, 7, 0, 0), (0, 6, 0, 0), (255, 255, 0, 0))
    )


BC7_CONFIG = _build_bc7_config()

# Signature ranks whose mode-2 partition assignment is inferred from anchor
# positions and order only; strict mode refuses chunks that reference them.
BC7_CONFIG_INFERRED = frozenset((149, 151, 152, 153, 246, 248, 251, 252, 253, 254))

_EMPTY_BC6H_EH = tuple(((0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)) for _ in range(256))
_EMPTY_BC6H_IH = tuple((0,) * 16 for _ in range(256))
_EMPTY_BC6H_CLS = (0,) * 256

_EMPTY_BC7_EP = tuple((0,) * 24 for _ in range(256))
_EMPTY_BC7_IX = tuple((0,) * 32 for _ in range(256))

_BC7_STATIC_CACHE = None
_FILE_CACHE = {}


def _bc7_static():
    """Return unpacked public D3D11/Khronos BC7 partition/anchor/signature tables."""
    global _BC7_STATIC_CACHE
    if _BC7_STATIC_CACHE is None:
        part2 = tuple(
            tuple((mask >> p) & 1 for p in range(16)) for mask in _BC7_PART2_PACKED
        )
        part3 = tuple(
            tuple((mask >> (2 * p)) & 3 for p in range(16)) for mask in _BC7_PART3_PACKED
        )
        cells = sorted(
            ((a, b) for a in range(32) for b in range(16)),
            key=lambda ab: ((ab[0] + 1) * (ab[1] + 1), ab[0]),
        )
        rank_of = [-1] * 512
        for rank, (a, b) in enumerate(cells):
            if rank < len(BC7_CONFIG):
                rank_of[a * 16 + b] = rank
        _BC7_STATIC_CACHE = {
            "partition2": part2,
            "partition3": part3,
            "anchor2": BC7_ANCHOR2,
            "anchor3a": BC7_ANCHOR3A,
            "anchor3b": BC7_ANCHOR3B,
            "config": BC7_CONFIG,
            "inferred": BC7_CONFIG_INFERRED,
            "rank_of": tuple(rank_of),
        }
    return _BC7_STATIC_CACHE


def _read_history_section(history, codec_key, marker_key):
    """Resolve `history` (None, dict, JSON file, or directory) for one codec."""
    if history is None:
        return None
    if isinstance(history, dict):
        if codec_key in history:
            return history[codec_key]
        return history if marker_key in history else None
    path = os.fspath(history)
    if os.path.isdir(path):
        candidate = os.path.join(path, f"{codec_key}.json")
        if not os.path.isfile(candidate):
            return None
        path = candidate
    abspath = os.path.abspath(path)
    mtime = os.path.getmtime(abspath)
    cached = _FILE_CACHE.get(abspath)
    if cached is not None and cached[0] == mtime:
        data = cached[1]
    else:
        with open(abspath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object")
        _FILE_CACHE[abspath] = (mtime, data)
    if codec_key in data:
        return data[codec_key]
    return data if marker_key in data else None


def _iter_entries(obj, count=256):
    """Yield `(index, value)` pairs from a 256-list or sparse `{index: value}` dict."""
    if obj is None:
        return
    if isinstance(obj, list):
        if len(obj) != count:
            raise ValueError(f"expected {count} entries, got {len(obj)}")
        for i, v in enumerate(obj):
            yield i, v
    elif isinstance(obj, dict):
        for k, v in obj.items():
            i = int(k)
            if not 0 <= i < count:
                raise ValueError(f"history entry index {i} outside 0..{count - 1}")
            yield i, v
    else:
        raise ValueError("history table must be a 256-element list or index-keyed dict")


def _flatten_bc7_entry(val, expected_len):
    """Flatten nested `[3][2][4]` / `[2][16]` or flat `24`/`32` BC7 entry to a tuple of ints."""
    out = []

    def _walk(x):
        if isinstance(x, (list, tuple)):
            for item in x:
                _walk(item)
        else:
            out.append(int(x))

    _walk(val)
    if len(out) != expected_len:
        raise ValueError(f"expected {expected_len} integers in BC7 history entry, got {len(out)}")
    return tuple(out)


def load_bc6h(history=None):
    """Return `(endpoint_history, index_history, endpoint_class, index_class)`.

    With `history=None`, returns empty/unknown tables (class `0` for all 256
    entries) so self-contained BC6H chunks still decode strictly without any
    external file. When `history` is a local JSON file, directory containing
    `bc6h.json`, or dict, populates the BC6H initial history tables from it.
    """
    sec = _read_history_section(history, "bc6h", "endpointHistory")
    if sec is None:
        return _EMPTY_BC6H_EH, _EMPTY_BC6H_IH, _EMPTY_BC6H_CLS, _EMPTY_BC6H_CLS
    eh = list(_EMPTY_BC6H_EH)
    ih = list(_EMPTY_BC6H_IH)
    ec = list(_EMPTY_BC6H_CLS)
    ic = list(_EMPTY_BC6H_CLS)
    for i, channels in _iter_entries(sec.get("endpointHistory")):
        if len(channels) != 3 or any(len(ch) != 4 for ch in channels):
            raise ValueError(f"BC6H endpointHistory[{i}] must be 3x4 integers")
        eh[i] = tuple(tuple(int(v) for v in ch) for ch in channels)
    for i, pixels in _iter_entries(sec.get("indexHistory")):
        if len(pixels) != 16:
            raise ValueError(f"BC6H indexHistory[{i}] must have 16 integers")
        ih[i] = tuple(int(v) for v in pixels)
    for i, cls in _iter_entries(sec.get("endpointClass")):
        ec[i] = int(cls)
    for i, cls in _iter_entries(sec.get("indexClass")):
        ic[i] = int(cls)
    return tuple(eh), tuple(ih), tuple(ec), tuple(ic)


def load_bc7(history=None):
    """Return the BC7 partition, anchor, signature, and history tables.

    With `history=None`, built-in history slots have depth `0` (unknown) so
    self-contained BC7 chunks decode strictly without external data while any
    reference to built-in history cleanly refuses. When `history` is a local
    JSON file, directory containing `bc7.json`, or dict, loads the BC7 initial
    history tables from it.
    """
    static = _bc7_static()
    sec = _read_history_section(history, "bc7", "historyEndpoints")
    if sec is None:
        return {
            **static,
            "history_endpoints": _EMPTY_BC7_EP,
            "history_endpoint_bits": _EMPTY_BC7_EP,
            "history_endpoint_confirmed_bits": _EMPTY_BC7_EP,
            "history_indices": _EMPTY_BC7_IX,
            "history_index_bits": _EMPTY_BC7_IX,
            "history_index_confirmed_bits": _EMPTY_BC7_IX,
            "last_resort": frozenset(),
        }
    ep = list(_EMPTY_BC7_EP)
    ep_b = list(_EMPTY_BC7_EP)
    ep_cb = list(_EMPTY_BC7_EP)
    ix = list(_EMPTY_BC7_IX)
    ix_b = list(_EMPTY_BC7_IX)
    ix_cb = list(_EMPTY_BC7_IX)
    for i, v in _iter_entries(sec.get("historyEndpoints")):
        ep[i] = _flatten_bc7_entry(v, 24)
    for i, v in _iter_entries(sec.get("historyEndpointBits")):
        ep_b[i] = _flatten_bc7_entry(v, 24)
    for i, v in _iter_entries(sec.get("historyEndpointConfirmedBits")):
        ep_cb[i] = _flatten_bc7_entry(v, 24)
    for i, v in _iter_entries(sec.get("historyIndices")):
        ix[i] = _flatten_bc7_entry(v, 32)
    for i, v in _iter_entries(sec.get("historyIndexBits")):
        ix_b[i] = _flatten_bc7_entry(v, 32)
    for i, v in _iter_entries(sec.get("historyIndexConfirmedBits")):
        ix_cb[i] = _flatten_bc7_entry(v, 32)
    # Mid-range fill for endpoints known to 0 < d < 8 leading bits.
    # Readers taking <= d bits shift the low bits away unchanged.
    for i in range(256):
        depth = ep_b[i]
        if any(0 < d < 8 for d in depth):
            row = ep[i]
            ep[i] = tuple(
                ((v >> (8 - d) << (8 - d)) | (1 << (7 - d))) if 0 < d < 8 else v
                for v, d in zip(row, depth)
            )
    last_resort = set()
    for item in sec.get("historyEndpointLastResort") or ():
        if len(item) == 4:
            k, sub, e, c = (int(x) for x in item)
            last_resort.add((k, sub * 8 + e * 4 + c))
        elif len(item) == 2:
            last_resort.add((int(item[0]), int(item[1])))
        else:
            raise ValueError("historyEndpointLastResort entries must have 2 or 4 integers")
    return {
        **static,
        "history_endpoints": tuple(ep),
        "history_endpoint_bits": tuple(ep_b),
        "history_endpoint_confirmed_bits": tuple(ep_cb),
        "history_indices": tuple(ix),
        "history_index_bits": tuple(ix_b),
        "history_index_confirmed_bits": tuple(ix_cb),
        "last_resort": frozenset(last_resort),
    }
````

## tools/bcpack.py

SHA-256 `e9233c26416373cedd700cf2825d8a34c7d65f67da35423c27345144e4fe1422`

````python
"""Clean-room BCPack bitstream decoder (Python standard library only).

Implements the Xbox Series DirectStorage BCPack entropy layer (interleaved
12/16-lane 16-bit rANS with 8-byte/cycle prefetch scheduling and exponential
frequency tables) and block rebuilders for all six active modes: BC1, BC3,
BC4, BC5, BC6H and BC7 (codecs 1, 3, 4, 5, 6 and 7).

Codec identifiers follow `DSTORAGE_BCPACK_MODE` (matching `tools/ttpf_mips.py`
and `docs/textures.md`):
    1 = BC1, 3 = BC3, 4 = BC4, 5 = BC5, 6 = BC6H, 7 = BC7.

Strict decoding (`decode(..., allow_provisional=False)`, the default) refuses
any chunk that depends on an unconfirmed built-in history entry or inferred BC7
signature. Pass `allow_provisional=True` (or use `decode_with_info`) to allow
provisional entries and inspect which ones were used.

See `docs/textures.md` for the bitstream specification and provenance.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bcpack_tables as _tables  # noqa: E402
import bcpack_tables_bptc as _bptc  # noqa: E402

# rANS and lane-array constants
RANS_L = 1 << 24
MAX_WIDTH = 10
PREFETCH_BUDGET = 8
MAX_VIRTUAL_ZEROS = 8

CODEC_NAMES = {
    1: "BC1",
    3: "BC3",
    4: "BC4",
    5: "BC5",
    6: "BC6H",
    7: "BC7",
}

# Bytes represented by one lane symbol-tuple (BC3/BC5/BC6H/BC7 use 2 elements per 16-byte block).
ELEMENT_BYTES = 8

BLOCK_BYTES = {
    1: 8,
    3: 16,
    4: 8,
    5: 16,
    6: 16,
    7: 16,
}

# Default per-lane symbol widths (bits) for each DSTORAGE_BCPACK_MODE.
LANE_WIDTHS = {
    1: (8, 8, 5, 6, 5, 5, 6, 5, 8, 8, 8, 8),
    3: (4, 4, 8, 6, 6, 6, 6, 5, 6, 5, 8, 8),
    4: (8, 8, 8, 8, 6, 6, 6, 6, 6, 6, 6, 6),
    5: (4, 4, 8, 8, 6, 6, 6, 6, 6, 6, 6, 6),
    6: (4, 4, 8, 8, 8, 5, 5, 5, 6, 6, 6, 8, 8, 8, 8, 5),
    7: (4, 4, 8, 8, 8, 8, 8, 7, 7, 5, 6, 8, 8, 8, 8, 5),
}

ALL_CODECS = frozenset(CODEC_NAMES)
SUPPORTED_REBUILD_CODECS = frozenset({1, 3, 4, 5, 6, 7})


class BcpackError(ValueError):
    """Raised when a BCPack stream fails structural or rANS validation."""


class BcpackProvisionalError(BcpackError):
    """Raised when strict decoding encounters an unconfirmed or unknown history entry."""


class BcpackUnsupportedCodec(NotImplementedError):
    """Raised when a BCPack codec has no block rebuilder yet."""


class _Model:
    """16-bit rANS banded frequency model for one (symbol_width, q) pair."""

    __slots__ = ("w", "freq", "base")

    def __init__(self, w, freq):
        self.w = w
        self.freq = freq
        base = []
        acc = 0
        for p, f in enumerate(freq):
            base.append(acc)
            acc += f * (1 if p == 0 else 1 << (p - 1))
        if acc != 65536:
            raise BcpackError(f"probability table ({w}) does not sum to 65536 (got {acc})")
        self.base = tuple(base)

    def lookup(self, cf):
        p = self.w
        base = self.base
        while p > 0 and cf < base[p]:
            p -= 1
        return 0 if p == 0 else (1 << (p - 1)) + (cf - base[p]) // self.freq[p]

    def advance(self, s, x):
        p = s.bit_length()
        f = self.freq[p]
        c = self.base[p] + f * (s - (0 if p == 0 else 1 << (p - 1)))
        if c == 0:
            f, c = f - 1, 1
        return f * (x >> 16) + (x & 0xFFFF) - c


_MODEL_CACHE = {}


def _get_model(w, q):
    key = (w, q)
    m = _MODEL_CACHE.get(key)
    if m is None:
        freq = _tables.PROB_TABLES.get(key)
        if freq is None:
            return None
        m = _Model(w, freq)
        _MODEL_CACHE[key] = m
    return m


def _decode_lanes_raw(raw, widths, nsym):
    """Decode the interleaved rANS lane array into one symbol list per lane.

    Returns `(lanes, bytes_used)`. Raises `BcpackError` if any fragment fails
    to land at the exact rANS lower bound `RANS_L`, runs out of input, or
    produces an out-of-range symbol.
    """
    nl = len(widths)
    HDR0, HDR1, HDR2, PROC = 0, 1, 2, 3
    L = RANS_L
    ctrl = [HDR0] * nl
    out_rem = [nsym] * nl
    w = [0] * nl
    q = [0] * nl
    h3 = [0] * nl
    flush = [0] * nl
    done = [nsym <= 0] * nl
    full = [False] * nl
    held = [False] * nl
    vz = [0] * nl
    inbuf = [0] * nl
    sym = [0] * nl
    in_rem = [0] * nl
    p0 = [0] * nl
    p1 = [0] * nl
    model = [None] * nl
    slotfull = [False] * nl
    slotval = [0] * nl
    stall = [False] * nl
    out = [[] for _ in range(nl)]
    pos = 0
    nraw = len(raw)

    def fail(msg, lane):
        raise BcpackError(
            f"lane {lane} (width {w[lane]}, q {q[lane]}) at input byte {pos}: {msg}"
        )

    while True:
        if all(done[i] and not slotfull[i] for i in range(nl)):
            return out, pos

        # Phase 1: state update, prefetch arbitration (at most 8 bytes/cycle),
        # and symbol release for non-stalled lanes.
        left = PREFETCH_BUDGET
        for i in range(nl):
            if done[i]:
                stall[i] = True
                continue
            if held[i] and slotfull[i]:
                stall[i] = True
                continue
            stall[i] = False
            if ctrl[i] == PROC:
                p0[i] = model[i].advance(sym[i], p1[i]) if held[i] else p1[i]
            if not full[i] and (ctrl[i] != PROC or in_rem[i] > 0):
                if left == 0:
                    stall[i] = True
                    continue
                if pos >= nraw:
                    fail("input ran out", i)
                inbuf[i] = raw[pos]
                pos += 1
                full[i] = True
                left -= 1
            if held[i]:
                slotfull[i] = True
                slotval[i] = sym[i]
                held[i] = False

        # Phase 2: header parsing, byte merge, virtual zero fill on flush, and symbol lookup.
        for i in range(nl):
            if done[i] or stall[i]:
                continue
            c = ctrl[i]
            if c == HDR0:
                if not full[i]:
                    continue
                h = inbuf[i]
                q[i] = h & 15
                flush[i] = (h >> 4) & 1
                h3[i] = (h >> 5) & 1
                w[i] = widths[i] - (h >> 6)
                full[i] = False
                ctrl[i] = HDR1
                vz[i] = 0
            elif c == HDR1:
                if not full[i]:
                    continue
                full[i] = False
                wi = w[i]
                if not 1 <= wi <= MAX_WIDTH:
                    fail("symbol width out of range", i)
                m = _get_model(wi, q[i])
                if m is None:
                    fail("probability table for this width and q is not known", i)
                model[i] = m
                if h3[i]:
                    in_rem[i] = inbuf[i]
                    ctrl[i] = HDR2
                else:
                    in_rem[i] = inbuf[i] + 1
                    ctrl[i] = PROC
            elif c == HDR2:
                if not full[i]:
                    continue
                in_rem[i] = ((inbuf[i] << 8) | (in_rem[i] & 0xFF)) + 257
                ctrl[i] = PROC
                full[i] = False
            else:
                st = p0[i]
                if st < L:
                    if in_rem[i] > 0:
                        if full[i]:
                            st = (st << 8) | inbuf[i]
                            in_rem[i] -= 1
                            full[i] = False
                            if in_rem[i] == 0 and flush[i]:
                                while st < L and st != 0 and vz[i] < MAX_VIRTUAL_ZEROS:
                                    st <<= 8
                                    vz[i] += 1
                    elif flush[i]:
                        if st == 0 or vz[i] >= MAX_VIRTUAL_ZEROS:
                            fail("fragment did not end at its home state", i)
                        while st < L and st != 0 and vz[i] < MAX_VIRTUAL_ZEROS:
                            st <<= 8
                            vz[i] += 1
                    else:
                        p1[i] = st
                        if out_rem[i] > 0:
                            ctrl[i] = HDR0
                        else:
                            done[i] = True
                        continue
                nxt = st > L and out_rem[i] > 0
                if nxt:
                    s = model[i].lookup(st & 0xFFFF)
                    sym[i] = s
                    out_rem[i] -= 1
                    if s >> w[i]:
                        fail("symbol outside its width", i)
                held[i] = nxt
                p1[i] = st
                if in_rem[i] == 0:
                    if flush[i]:
                        if st == L:
                            if out_rem[i] > 0:
                                ctrl[i] = HDR0
                                p0[i] = 0
                                p1[i] = 0
                            else:
                                done[i] = True
                        elif st > L and not nxt:
                            fail("fragment did not end at its home state", i)
                    elif out_rem[i] == 0 and not nxt:
                        done[i] = True
                elif st == L or (out_rem[i] == 0 and not nxt and st > L):
                    fail("fragment did not end at its home state", i)

        # Phase 3: emit one synchronized element when every active lane has filled its slot.
        ready = True
        anyfull = False
        for i in range(nl):
            if slotfull[i]:
                anyfull = True
            elif not (done[i] and not held[i]):
                ready = False
                break
        if ready and anyfull:
            for i in range(nl):
                if slotfull[i]:
                    out[i].append(slotval[i])
                    slotfull[i] = False
        for i in range(nl):
            if done[i] and held[i] and not slotfull[i]:
                slotfull[i] = True
                slotval[i] = sym[i]
                held[i] = False


def decode_lanes(raw, codec, out_size):
    """Entropy layer: decode `raw` into per-lane symbol lists and bytes consumed.

    Works for all six active codecs (`1, 3, 4, 5, 6, 7`). Trailing non-zero
    bytes after the last lane finishes are rejected.
    """
    if codec not in LANE_WIDTHS:
        raise BcpackError(f"unsupported BCPack codec id: {codec}")
    if out_size < 0 or out_size % BLOCK_BYTES[codec] != 0:
        raise BcpackError(
            f"decoded size {out_size} is not a whole number of {CODEC_NAMES[codec]} blocks"
        )
    nsym = out_size // ELEMENT_BYTES
    data = memoryview(raw)
    lanes, used = _decode_lanes_raw(data, LANE_WIDTHS[codec], nsym)
    if any(data[used:]):
        raise BcpackError("non-zero data left over after the last lane finished")
    return lanes, used


def _unzig(v):
    return -((v + 1) >> 1) if (v & 1) else (v >> 1)


def _inter(a, b, n):
    d = 0
    for k in range(n):
        d |= (((a >> k) & 1) << (2 * k)) | (((b >> k) & 1) << (2 * k + 1))
    return d


def _inter8(a, b):
    return _inter(a, b, 4)


# 4-bit de-interleave lookup tables for 8-bit index-pair symbols (even / odd bits).
_DEINT = (
    tuple(
        ((s >> 0) & 1) | (((s >> 2) & 1) << 1) | (((s >> 4) & 1) << 2) | (((s >> 6) & 1) << 3)
        for s in range(256)
    ),
    tuple(
        ((s >> 1) & 1) | (((s >> 3) & 1) << 1) | (((s >> 5) & 1) << 2) | (((s >> 7) & 1) << 3)
        for s in range(256)
    ),
)


def _loose_limit(nblocks):
    """Maximum undetermined blocks permitted in provisional mode (1 in 1,024, min 2)."""
    return max(2, nblocks // 1024)


def _bc1_blocks(lanes, nblocks, provisional):
    if any(lanes[1]):
        raise BcpackError("BC1 lane 1 is non-zero (unexpected)")
    quad = _tables.BC1_QUADRANT
    confirmed = _tables.BC1_HISTORY_CONFIRMED
    loose = _tables.BC1_HISTORY_PROVISIONAL
    out = bytearray(nblocks * 8)
    hist = [None] * nblocks
    mods = (32, 64, 32, 32, 64, 32)
    l0 = lanes[0]
    cols = lanes[2:8]
    q0, q1, q2, q3 = lanes[8:12]
    for i in range(nblocks):
        v = l0[i]
        d = 256 - ((v + 1) >> 1) if (v & 1) else (v >> 1)
        if d == 0:
            base = (0, 0, 0, 0, 0, 0)
        elif i - d >= 0:
            base = hist[i - d]
        else:
            entry = 256 + i - d
            base = confirmed.get(entry)
            if base is None:
                if provisional is not None and entry in loose:
                    base = loose[entry]
                    provisional.add(f"BC1 history {entry}")
                else:
                    state = "unconfirmed" if entry in loose else "unknown"
                    raise BcpackProvisionalError(
                        f"BC1 block {i} references {state} built-in history entry {entry}"
                    )
        e0 = (base[0] + _unzig(cols[0][i])) % mods[0]
        e1 = (base[1] + _unzig(cols[1][i])) % mods[1]
        e2 = (base[2] + _unzig(cols[2][i])) % mods[2]
        e3 = (base[3] + _unzig(cols[3][i])) % mods[3]
        e4 = (base[4] + _unzig(cols[4][i])) % mods[4]
        e5 = (base[5] + _unzig(cols[5][i])) % mods[5]
        hist[i] = (e0, e1, e2, e3, e4, e5)
        c0 = (e0 << 11) | (e1 << 5) | e2
        c1 = (e3 << 11) | (e4 << 5) | e5
        a, b, c, dd = quad[q0[i]], quad[q1[i]], quad[q2[i]], quad[q3[i]]
        # Quadrant byte: pixels TL, TR, BL, BR in bits 0-1, 2-3, 4-5, 6-7.
        struct.pack_into(
            "<HHBBBB",
            out,
            i * 8,
            c0,
            c1,
            (a & 15) | ((b & 15) << 4),
            (a >> 4) | ((b >> 4) << 4),
            (c & 15) | ((dd & 15) << 4),
            (c >> 4) | ((dd >> 4) << 4),
        )
    return bytes(out)


_BC3_MODS = (256, 256, 32, 64, 32, 32, 64, 32)
_BC3_NONE = (128, 128, 0, 0, 0, 0, 0, 0)


def _bc3_blocks(lanes, nblocks, provisional):
    if any(lanes[1]):
        raise BcpackError("BC3 lane 1 is non-zero (unexpected)")
    pairs = _tables.BC3_ALPHA_PAIR
    quads = _tables.BC3_COLOUR_QUADRANT
    confirmed = _tables.BC3_HISTORY_CONFIRMED
    loose = _tables.BC3_HISTORY_PROVISIONAL
    out = bytearray(nblocks * 16)
    hist = [None] * nblocks
    lost = [False] * nblocks
    l0, alpha = lanes[0], lanes[2]
    rows = lanes[3:7]
    lr, lg, lb = lanes[7], lanes[8], lanes[9]
    top, bottom = lanes[10], lanes[11]
    unknown = set()
    mods = _BC3_MODS
    for i in range(nblocks):
        a, b = 2 * i, 2 * i + 1
        d = _unzig(_inter8(l0[a], l0[b])) & 255
        if d == 0:
            base = _BC3_NONE
        elif i - d >= 0:
            base = hist[i - d]
            lost[i] = lost[i - d]
        else:
            entry = 256 + i - d
            base = confirmed.get(entry)
            if base is None and entry in loose:
                if provisional is None:
                    raise BcpackProvisionalError(
                        f"BC3 block {i} references unconfirmed built-in history entry {entry}"
                    )
                base = loose[entry]
                provisional.add(f"BC3 history {entry}")
            if base is None:
                if provisional is None:
                    raise BcpackProvisionalError(
                        f"BC3 block {i} references unknown built-in history entry {entry}"
                    )
                base = _BC3_NONE
                lost[i] = True
                unknown.add(entry)
        dz = (alpha[a], alpha[b], lr[a], lg[a], lb[a], lr[b], lg[b], lb[b])
        e = tuple((base[k] + _unzig(dz[k])) % mods[k] for k in range(8))
        hist[i] = e
        bits = 0
        for r in range(4):
            left, right = pairs[rows[r][a]], pairs[rows[r][b]]
            bits |= (left[0] | (left[1] << 3) | (right[0] << 6) | (right[1] << 9)) << (12 * r)
        at = i * 16
        out[at] = e[0]
        out[at + 1] = e[1]
        out[at + 2:at + 8] = bits.to_bytes(6, "little")
        c0 = (e[2] << 11) | (e[3] << 5) | e[4]
        c1 = (e[5] << 11) | (e[6] << 5) | e[7]
        qa, qb = quads[top[a]], quads[top[b]]
        qc, qd = quads[bottom[a]], quads[bottom[b]]
        struct.pack_into(
            "<HHBBBB",
            out,
            at + 8,
            c0,
            c1,
            (qa & 15) | ((qb & 15) << 4),
            (qa >> 4) | ((qb >> 4) << 4),
            (qc & 15) | ((qd & 15) << 4),
            (qc >> 4) | ((qd >> 4) << 4),
        )
    if unknown:
        total = sum(lost)
        if total > _loose_limit(nblocks):
            raise BcpackProvisionalError(
                f"BC3 chunk has {total}/{nblocks} blocks from unknown built-in history entries"
            )
        provisional.add(f"BC3 unknown history {sorted(unknown)} ({total} blocks)")
    return bytes(out)


def _bc4_blocks(lanes, nblocks, provisional):
    if any(lanes[1]):
        raise BcpackError("BC4 lane 1 is non-zero (unexpected)")
    pairs = _tables.BC4_PAIR
    confirmed = _tables.BC4_HISTORY_CONFIRMED
    loose = _tables.BC4_HISTORY_PROVISIONAL
    out = bytearray(nblocks * 8)
    hist = [None] * nblocks
    l0, l2, l3 = lanes[0], lanes[2], lanes[3]
    rows = lanes[4:12]
    for i in range(nblocks):
        v = l0[i]
        d = 256 - ((v + 1) >> 1) if (v & 1) else (v >> 1)
        if d == 0:
            base = (128, 128)
        elif i - d >= 0:
            base = hist[i - d]
        else:
            entry = 256 + i - d
            base = confirmed.get(entry)
            if base is None:
                if provisional is not None and entry in loose:
                    base = loose[entry]
                    provisional.add(f"BC4 history {entry}")
                else:
                    state = "unconfirmed" if entry in loose else "unknown"
                    raise BcpackProvisionalError(
                        f"BC4 block {i} references {state} built-in history entry {entry}"
                    )
        a0 = (base[0] + _unzig(l2[i])) & 255
        a1 = (base[1] + _unzig(l3[i])) & 255
        hist[i] = (a0, a1)
        bits = 0
        for r in range(4):
            left, right = pairs[rows[2 * r][i]], pairs[rows[2 * r + 1][i]]
            bits |= (left[0] | (left[1] << 3) | (right[0] << 6) | (right[1] << 9)) << (12 * r)
        at = i * 8
        out[at] = a0
        out[at + 1] = a1
        out[at + 2:at + 8] = bits.to_bytes(6, "little")
    return bytes(out)


def _bc5_blocks(lanes, nblocks, provisional):
    if any(lanes[1]):
        raise BcpackError("BC5 lane 1 is non-zero (unexpected)")
    pairs = _tables.BC5_PAIR
    confirmed = _tables.BC5_HISTORY_CONFIRMED
    loose = _tables.BC5_HISTORY_PROVISIONAL
    out = bytearray(nblocks * 16)
    hist = [None] * nblocks
    lost = [False] * nblocks
    l0, red, green = lanes[0], lanes[2], lanes[3]
    rows = lanes[4:12]
    unknown = set()
    for i in range(nblocks):
        a, b = 2 * i, 2 * i + 1
        d = _unzig(_inter8(l0[a], l0[b])) & 255
        if d == 0:
            base = (128, 128, 128, 128)
        elif i - d >= 0:
            base = hist[i - d]
            lost[i] = lost[i - d]
        else:
            entry = 256 + i - d
            base = confirmed.get(entry)
            if base is None and entry in loose:
                if provisional is None:
                    raise BcpackProvisionalError(
                        f"BC5 block {i} references unconfirmed built-in history entry {entry}"
                    )
                base = loose[entry]
                provisional.add(f"BC5 history {entry}")
            if base is None:
                if provisional is None:
                    raise BcpackProvisionalError(
                        f"BC5 block {i} references unknown built-in history entry {entry}"
                    )
                base = (128, 128, 128, 128)
                lost[i] = True
                unknown.add(entry)
        e = (
            (base[0] + _unzig(red[a])) & 255,
            (base[1] + _unzig(red[b])) & 255,
            (base[2] + _unzig(green[a])) & 255,
            (base[3] + _unzig(green[b])) & 255,
        )
        hist[i] = e
        at = i * 16
        for ch in range(2):
            bits = 0
            for r in range(4):
                left, right = pairs[rows[4 * ch + r][a]], pairs[rows[4 * ch + r][b]]
                bits |= (left[0] | (left[1] << 3) | (right[0] << 6) | (right[1] << 9)) << (12 * r)
            out[at + 8 * ch] = e[2 * ch]
            out[at + 8 * ch + 1] = e[2 * ch + 1]
            out[at + 8 * ch + 2:at + 8 * ch + 8] = bits.to_bytes(6, "little")
    if unknown:
        total = sum(lost)
        if total > _loose_limit(nblocks):
            raise BcpackProvisionalError(
                f"BC5 chunk has {total}/{nblocks} blocks from unknown built-in history entries"
            )
        provisional.add(f"BC5 unknown history {sorted(unknown)} ({total} blocks)")
    return bytes(out)


# BC6H ------------------------------------------------------------------------

# Mode index (1..14, where mode = lane15[2*i] + 1) -> D3D11/Khronos mode bits.
_BC6H_CODE = (
    0, 0x00, 0x01, 0x02, 0x06, 0x0A, 0x0E, 0x12,
    0x16, 0x1A, 0x1E, 0x03, 0x07, 0x0B, 0x0F,
)

# Mode code -> (transformed, base_bits, (dr, dg, db), regions).
_BC6H_INFO = {
    0x00: (1, 10, (5, 5, 5), 2),
    0x01: (1, 7, (6, 6, 6), 2),
    0x02: (1, 11, (5, 4, 4), 2),
    0x06: (1, 11, (4, 5, 4), 2),
    0x0A: (1, 11, (4, 4, 5), 2),
    0x0E: (1, 9, (5, 5, 5), 2),
    0x12: (1, 8, (6, 5, 5), 2),
    0x16: (1, 8, (5, 6, 5), 2),
    0x1A: (1, 8, (5, 5, 6), 2),
    0x1E: (0, 6, (6, 6, 6), 2),
    0x03: (0, 10, (10, 10, 10), 1),
    0x07: (1, 11, (9, 9, 9), 1),
    0x0B: (1, 12, (8, 8, 8), 1),
    0x0F: (1, 16, (4, 4, 4), 1),
}

# Standard D3D11/Khronos BC6H header bit layouts (LSB-first after the 2- or 5-bit mode).
_BC6H_LAYOUT = {
    0x00: "gy4 by4 bz4 rw10 gw10 bw10 rx5 gz4 gy4_ gx5 bz0 gz4_ bx5 bz1 by4_ ry5 bz2 rz5 bz3 d",
    0x01: "gy5 gz4 gz5 rw7 bz0 bz1 by4 gw7 by5 bz2 gy4 bw7 bz3 bz5 bz4 rx6 gy4_ gx6 gz4_ bx6 by4_ ry6 rz6 d",
    0x02: "rw10 gw10 bw10 rx5 rw:10 gy4_ gx4 gw:10 bz0 gz4_ bx4 bw:10 bz1 by4_ ry5 bz2 rz5 bz3 d",
    0x06: "rw10 gw10 bw10 rx4 rw:10 gz4 gy4_ gx5 gw:10 gz4_ bx4 bw:10 bz1 by4_ ry4 bz0 bz2 rz4 gy4 bz3 d",
    0x0A: "rw10 gw10 bw10 rx4 rw:10 by4 gy4_ gx4 gw:10 bz0 gz4_ bx5 bw:10 by4_ ry4 bz1 bz2 rz4 bz4 bz3 d",
    0x0E: "rw9 by4 gw9 gy4 bw9 bz4 rx5 gz4 gy4_ gx5 bz0 gz4_ bx5 bz1 by4_ ry5 bz2 rz5 bz3 d",
    0x12: "rw8 gz4 by4 gw8 bz2 gy4 bw8 bz3 bz4 rx6 gy4_ gx5 bz0 gz4_ bx5 bz1 by4_ ry6 rz6 d",
    0x16: "rw8 bz0 by4 gw8 gy5 gy4 bw8 gz5 bz4 rx5 gz4 gy4_ gx6 gz4_ bx5 bz1 by4_ ry5 bz2 rz5 bz3 d",
    0x1A: "rw8 bz1 by4 gw8 by5 gy4 bw8 bz5 bz4 rx5 gz4 gy4_ gx5 bz0 gz4_ bx6 by4_ ry5 bz2 rz5 bz3 d",
    0x1E: "rw6 gz4 bz0 bz1 by4 gw6 gy5 by5 bz2 gy4 bw6 gz5 bz3 bz5 bz4 rx6 gy4_ gx6 gz4_ bx6 by4_ ry6 rz6 d",
    0x03: "rw10 gw10 bw10 rx10 gx10 bx10",
    0x07: "rw10 gw10 bw10 rx9 rw:10 gx9 gw:10 bx9 bw:10",
    0x0B: "rw10 gw10 bw10 rx8 rw:11-10 gx8 gw:11-10 bx8 bw:11-10",
    0x0F: "rw10 gw10 bw10 rx4 rw:15-10 gx4 gw:15-10 bx4 bw:15-10",
}

_BC6H_FIELD_MAP = {
    "rw": (0, 0), "gw": (1, 0), "bw": (2, 0),
    "rx": (0, 1), "gx": (1, 1), "bx": (2, 1),
    "ry": (0, 2), "gy": (1, 2), "by": (2, 2),
    "rz": (0, 3), "gz": (1, 3), "bz": (2, 3),
}

_BC6H_NONE_E = ((0x8000, 0x200, 0x20, 0x20),) * 3
_BC6H_NONE_I = (8,) * 16
_BC6H_PLANS = {}


def _bc6h_plan(code):
    """Cached `(plan, header_bits)` for a BC6H mode code.

    Each plan item is `(channel, endpoint_slot, bit_index, stream_pos)` with
    `channel == -1` for the 5-bit partition field `d`.
    """
    cached = _BC6H_PLANS.get(code)
    if cached is not None:
        return cached
    pos = 2 if code < 2 else 5
    plan = []
    for token in _BC6H_LAYOUT[code].split():
        if token == "d":
            for b in range(5):
                plan.append((-1, -1, b, pos + b))
            pos += 5
        elif ":" in token:
            name, span = token.split(":")
            c, q = _BC6H_FIELD_MAP[name]
            hi, lo = (int(x) for x in span.split("-")) if "-" in span else (int(span), int(span))
            for b in range(hi, lo - 1, -1):
                plan.append((c, q, b, pos))
                pos += 1
        elif token.endswith("_"):
            name, n = token[:2], int(token[2:-1])
            c, q = _BC6H_FIELD_MAP[name]
            for b in range(n):
                plan.append((c, q, b, pos + b))
            pos += n
        else:
            name, n = token[:2], int(token[2:])
            c, q = _BC6H_FIELD_MAP[name]
            if name[1] in "wx" or name in ("ry", "rz"):
                for b in range(n):
                    plan.append((c, q, b, pos + b))
                pos += n
            else:
                plan.append((c, q, n, pos))
                pos += 1
    res = (tuple(plan), pos)
    _BC6H_PLANS[code] = res
    return res


def _bc6h_stream_w(mode, w):
    """Map BCPack's base endpoint `w` into the D3D11/Khronos BC6H bit order."""
    if mode == 13:
        return (w & 0x3FF) | (((w >> 10) & 1) << 11) | (((w >> 11) & 1) << 10)
    if mode == 14:
        out = w & 0x3FF
        for b in range(10, 16):
            out |= ((w >> b) & 1) << (25 - b)
        return out
    return w


def _bc6h_blocks(lanes, nblocks, provisional, *, history=None):
    """Rebuild `nblocks` 16-byte BC6H blocks from the 16 BCPack lanes.

    With `history=None`, no built-in BC6H initial history is loaded, so strict
    mode (`provisional is None`) accepts only self-contained chunks whose delta
    chains stay within the chunk (`d == 0` or `d <= i`). Pass a locally
    generated `history` JSON file/directory to supply built-in history entries.
    """
    if len(lanes[0]) != 2 * nblocks:
        raise BcpackError("BC6H lane length does not match the block count")
    eh_table, ih_table, eclass, iclass = _bptc.load_bc6h(history)
    anchor2 = _bptc.BC7_ANCHOR2
    out = bytearray(nblocks * 16)
    st_e = [None] * nblocks
    st_i = [None] * nblocks
    eroot = [-1] * nblocks
    iroot = [-1] * nblocks
    ends = {}
    idxs = {}
    violations = 0
    l0, l1, l15 = lanes[0], lanes[1], lanes[15]
    deint0, deint1 = _DEINT

    for i in range(nblocks):
        a, b = 2 * i, 2 * i + 1
        m_sym = l15[a]
        if m_sym > 13:
            raise BcpackError(f"BC6H block {i} mode symbol {m_sym} outside 0..13")
        mode = m_sym + 1
        code = _BC6H_CODE[mode]
        trans, base, deltas, reg = _BC6H_INFO[code]
        part = l15[b] if l15[b] < 31 else 31

        di = _inter8(l1[a], l1[b])
        de = (di + _unzig(_inter8(l0[a], l0[b]))) & 255
        if de == 0:
            eref = _BC6H_NONE_E
        elif i >= de:
            eref = st_e[i - de]
            eroot[i] = eroot[i - de]
        else:
            entry = 256 + i - de
            eref = eh_table[entry]
            eroot[i] = entry
        if eroot[i] >= 0:
            r = eroot[i]
            ends[r] = ends.get(r, 0) + 1

        if di == 0:
            iref = _BC6H_NONE_I
        elif i >= di:
            iref = st_i[i - di]
            iroot[i] = iroot[i - di]
        else:
            entry = 256 + i - di
            iref = ih_table[entry]
            iroot[i] = entry
        if iroot[i] >= 0:
            r = iroot[i]
            idxs[r] = idxs.get(r, 0) + 1

        mw = (1 << base) - 1
        w_shift = 16 - base
        f_block = [None, None, None]
        st_block = [None, None, None]
        for c in range(3):
            dc = deltas[c]
            mD = (1 << dc) - 1
            sh = 6 - dc if dc < 6 else 0
            dz0 = _unzig(_inter(lanes[2 + c][a], lanes[2 + c][b], 8))
            dz1 = _unzig(_inter(lanes[5 + c][a], lanes[5 + c][b], 5))
            dz2 = _unzig(lanes[8 + c][a])
            dz3 = _unzig(lanes[8 + c][b])
            r0, r1, r2, r3 = eref[c]
            w = ((r0 >> w_shift) + dz0) & mw
            x = ((r1 >> (10 - dc)) + dz1) & mD
            y = ((r2 >> sh) + dz2) & mD
            z = ((r3 >> sh) + dz3) & mD
            x10 = x << (10 - dc)
            if reg == 2:
                st_block[c] = (w << w_shift, x10, y << sh, z << sh)
                f_block[c] = (_bc6h_stream_w(mode, w), x, y, z)
            else:
                v = (w & mD) ^ ((1 << (dc - 1)) if trans == 1 else 0)
                low_y = (v >> (dc - 6)) if dc >= 6 else (v << sh)
                st_block[c] = (w << w_shift, x10, low_y, x10 >> 4)
                f_block[c] = (_bc6h_stream_w(mode, w), x, 0, 0)
        st_e[i] = (st_block[0], st_block[1], st_block[2])

        ibits = 3 if reg == 2 else 4
        imask = (1 << ibits) - 1
        ishift = 4 - ibits
        ix_block = [0] * 16
        si_block = [0] * 16
        for yy in range(4):
            sa = lanes[11 + yy][a]
            sb = lanes[11 + yy][b]
            row = yy * 4
            if yy < 3:
                d0, d1 = deint1[sa], deint0[sa]
                d2, d3 = deint1[sb], deint0[sb]
            else:
                d0, d1 = deint0[sa], deint1[sa]
                d2, d3 = deint0[sb], deint1[sb]
            for off, dv in ((0, d0), (1, d1), (2, d2), (3, d3)):
                p = row + off
                ix = ((iref[p] >> ishift) + _unzig(dv)) & imask
                ix_block[p] = ix
                si_block[p] = ix << ishift
        st_i[i] = tuple(si_block)

        second = anchor2[part] if reg == 2 else -1
        if ix_block[0] & (4 if reg == 2 else 8):
            violations += 1
        if reg == 2 and (ix_block[second] & 4):
            violations += 1

        plan, header = _bc6h_plan(code)
        acc = code
        for c, q, bit_idx, pos in plan:
            if c < 0:
                if (part >> bit_idx) & 1:
                    acc |= 1 << pos
            elif (f_block[c][q] >> bit_idx) & 1:
                acc |= 1 << pos
        at = header
        for p in range(16):
            nb = (ibits - 1) if (p == 0 or p == second) else ibits
            acc |= (ix_block[p] & ((1 << nb) - 1)) << at
            at += nb
        out[16 * i:16 * i + 16] = acc.to_bytes(16, "little")

    if provisional is None:
        unconf_e = [k for k in ends if eclass[k] != 3]
        unconf_i = [k for k in idxs if iclass[k] != 3]
        if unconf_e or unconf_i:
            k = unconf_e[0] if unconf_e else unconf_i[0]
            kind = "endpoint" if unconf_e else "index"
            cls = eclass[k] if unconf_e else iclass[k]
            state = "unknown" if cls == 0 else "unconfirmed"
            hint = " (pass --history <path>)" if history is None else ""
            raise BcpackProvisionalError(
                f"BC6H chunk references {state} built-in {kind} history entry {k}{hint}"
            )
        if violations:
            raise BcpackError(
                f"BC6H chunk has {violations} anchor pixel(s) with an inconsistent index"
            )
        return bytes(out)

    lost = (
        sum(c for k, c in ends.items() if eclass[k] == 0)
        + sum(c for k, c in idxs.items() if iclass[k] == 0)
    )
    missing = sorted(
        {f"endpoint {k}" for k in ends if eclass[k] == 0}
        | {f"index {k}" for k in idxs if iclass[k] == 0}
    )
    if lost > _loose_limit(nblocks):
        hint = " (pass --history <path>)" if history is None else ""
        raise BcpackProvisionalError(
            f"BC6H chunk has {lost}/{nblocks} blocks from unknown built-in history entries "
            f"({', '.join(missing[:6])}{', ...' if len(missing) > 6 else ''}){hint}"
        )
    if violations > _loose_limit(nblocks):
        raise BcpackProvisionalError(
            f"BC6H chunk has {violations} anchor pixels with an inconsistent index"
        )
    if missing:
        provisional.add(f"BC6H unknown history {', '.join(missing)} ({lost} blocks)")
    if violations:
        provisional.add(f"BC6H anchor index inconsistent in {violations} pixels")
    for name, entries, cls in (("endpoint", ends, eclass), ("index", idxs, iclass)):
        fitted = sorted(k for k in entries if cls[k] == 1)
        rough = sorted(k for k in entries if cls[k] == 2)
        if fitted:
            provisional.add(f"BC6H {name} history {', '.join(map(str, fitted))}")
        if rough:
            provisional.add(f"BC6H {name} history {', '.join(map(str, rough))} (last-resort)")
    return bytes(out)


# BC7 -------------------------------------------------------------------------

_B7_NS = (3, 2, 3, 2, 1, 1, 1, 2)
_B7_CB = (4, 6, 5, 7, 5, 7, 7, 5)
_B7_AB = (0, 0, 0, 0, 6, 8, 7, 5)
_B7_PK = (1, 2, 0, 1, 0, 0, 1, 1)      # 0=none, 1=per-endpoint p-bit, 2=shared per subset
_B7_IB = (3, 3, 2, 2, 3, 2, 4, 2)      # index bits of primary index set (lanes 11..14)
_B7_PB = (4, 6, 6, 6, 0, 0, 0, 6)      # partition field bits
_B7_LANE = ((2, 3, 4, 5), (6, 7, 8, 9), (10, 5, 9, -1))
_B7_ANCHOR = 8
_B7_PBIT = 16
_B7_SIGNATURE = 32
_B7_MIN_DEPTH = 4


def _bc7_field_bits(mode, rot):
    """Leading bits read from a stored endpoint byte for channels (R, G, B, A)."""
    w = [_B7_CB[mode], _B7_CB[mode], _B7_CB[mode], _B7_AB[mode]]
    if rot:
        w[rot - 1], w[3] = _B7_AB[mode], _B7_CB[mode]
    pk = _B7_PK[mode]
    return [w[c] + (1 if (pk and c == 0) else 0) if w[c] else 0 for c in range(4)]


def _bc7_check(lanes, nblocks, table, provisional, *, has_history=False):
    """Validate signatures and built-in history coverage for a BC7 chunk.

    In strict mode (`provisional is None`), raises `BcpackError` for unknown
    signatures and `BcpackProvisionalError` for inferred signatures or any
    unconfirmed/unknown built-in history entry. In provisional mode, populates
    `provisional` with descriptive labels and returns a list of `(kind, entry)`
    pairs whose depth is below `_B7_MIN_DEPTH` (or missing for indices).
    """
    cfg = table["config"]
    rank_of = table["rank_of"]
    l0, l1, l15 = lanes[0], lanes[1], lanes[15]
    ranks = set()
    for a, b in set(zip(l15[0::2], l15[1::2])):
        rank = rank_of[a * 16 + b] if a < 32 and b < 16 else -1
        if rank < 0 or cfg[rank][0] > 7 or cfg[rank][1] == 255:
            raise BcpackError(f"BC7 signature ({a}, {b}) is outside the signature table")
        ranks.add(rank)
    for rank in sorted(ranks & table["inferred"]):
        if provisional is None:
            raise BcpackProvisionalError(
                f"BC7 signature rank {rank} is inferred-only (unconfirmed)"
            )
        provisional.add(f"BC7 signature {rank}")

    need_e = {}
    need_i = {}
    for i in range(min(nblocks, 256)):
        rank = rank_of[l15[2 * i] * 16 + l15[2 * i + 1]]
        mode, _, rot, _ = cfg[rank]
        di = _inter8(l1[2 * i], l1[2 * i + 1])
        de = (di + _unzig(_inter8(l0[2 * i], l0[2 * i + 1]))) & 255
        if de > i:
            bits = _bc7_field_bits(mode, rot)
            row = need_e.setdefault(256 + i - de, [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
            for sub in range(_B7_NS[mode]):
                for c in range(4):
                    if bits[c] > row[sub][c]:
                        row[sub][c] = bits[c]
        if di > i:
            row = need_i.setdefault(256 + i - di, [0, 0])
            if _B7_IB[mode] > row[0]:
                row[0] = _B7_IB[mode]
            if mode in (4, 5):
                row[1] = 2

    unknown = []
    last_resort = table["last_resort"]
    checks = (
        ("endpoint", need_e, table["history_endpoint_bits"], table["history_endpoint_confirmed_bits"]),
        ("index", need_i, table["history_index_bits"], table["history_index_confirmed_bits"]),
    )
    for kinds, need, bits_t, conf_t in checks:
        for k, want in sorted(need.items()):
            if kinds == "endpoint":
                slots = [
                    (sub * 8 + e * 4 + c, want[sub][c])
                    for sub in range(3) for e in range(2) for c in range(4)
                    if want[sub][c]
                ]
            else:
                slots = [
                    (st * 16 + p, want[st])
                    for st in range(2) for p in range(16)
                    if want[st]
                ]
            weak = False
            missing = False
            shallow = 8
            bk = bits_t[k]
            ck = conf_t[k]
            for j, b in slots:
                if bk[j] < b:
                    missing = True
                    if bk[j] < shallow:
                        shallow = bk[j]
                if ck[j] < b:
                    weak = True
            if missing:
                if provisional is None:
                    hint = " (pass --history <path>)" if not has_history else ""
                    raise BcpackProvisionalError(
                        f"BC7 chunk references unknown built-in {kinds} history entry {k}{hint}"
                    )
                if kinds == "endpoint" and shallow >= _B7_MIN_DEPTH:
                    provisional.add(f"BC7 endpoint history {k} (top {shallow} bits known)")
                else:
                    unknown.append((kinds, k))
            elif weak:
                if provisional is None:
                    raise BcpackProvisionalError(
                        f"BC7 chunk references unconfirmed built-in {kinds} history entry {k}"
                    )
                provisional.add(f"BC7 {kinds} history {k}")
            if kinds == "endpoint" and provisional is not None:
                if any((k, j) in last_resort for j, _ in slots):
                    provisional.add(f"BC7 endpoint history {k} (last-resort)")
    return unknown


def _bc7_rebuild(lanes, nblocks, table):
    """Rebuild `nblocks` 16-byte BC7 blocks and per-block consistency status flags."""
    cfg = table["config"]
    rank_of = table["rank_of"]
    p2 = table["partition2"]
    p3 = table["partition3"]
    a2 = table["anchor2"]
    a3a = table["anchor3a"]
    a3b = table["anchor3b"]
    pre_e = table["history_endpoints"]
    pre_i = table["history_indices"]
    out = bytearray(16 * nblocks)
    status = [0] * nblocks
    eps = [None] * nblocks
    ixs = [None] * nblocks
    zero_e = (0,) * 24
    zero_i = (0,) * 32
    rows1 = (lanes[11], lanes[12], lanes[13], lanes[14])
    rows2 = (lanes[6], lanes[7], lanes[8], lanes[10])
    l0, l1, l15 = lanes[0], lanes[1], lanes[15]
    deint0, deint1 = _DEINT

    for i in range(nblocks):
        a, b = 2 * i, 2 * i + 1
        s15a, s15b = l15[a], l15[b]
        rank = rank_of[s15a * 16 + s15b] if s15a < 32 and s15b < 16 else -1
        if rank < 0 or cfg[rank][0] > 7:
            status[i] = _B7_SIGNATURE
            eps[i] = zero_e
            ixs[i] = zero_i
            continue
        mode, part, rot, isel = cfg[rank]
        st = 0
        di = _inter8(l1[a], l1[b])
        de = (di + _unzig(_inter8(l0[a], l0[b]))) & 255
        rep = zero_e if de == 0 else (eps[i - de] if i >= de else pre_e[256 + i - de])
        rix = zero_i if di == 0 else (ixs[i - di] if i >= di else pre_i[256 + i - di])

        ns = _B7_NS[mode]
        cb = _B7_CB[mode]
        ab = _B7_AB[mode]
        pk = _B7_PK[mode]
        w = [cb, cb, cb, ab]
        if rot:
            w[rot - 1], w[3] = ab, cb

        val = [[[0, 0, 0, 0], [0, 0, 0, 0]] for _ in range(3)]
        sep = [0] * 24
        pb = [[0, 0], [0, 0], [0, 0]]
        for sub in range(ns):
            lane_row = _B7_LANE[sub]
            base_sub = sub * 8
            for c in range(4):
                lane_idx = lane_row[c]
                wc = w[c]
                if not wc or lane_idx < 0:
                    continue
                bits = wc + (1 if (pk and c == 0) else 0)
                shift = 8 - bits
                mask = (1 << bits) - 1
                ln = lanes[lane_idx]
                v0 = ((rep[base_sub + c] >> shift) + _unzig(ln[a])) & mask
                v1 = ((rep[base_sub + 4 + c] >> shift) + _unzig(ln[b])) & mask
                val[sub][0][c] = v0
                val[sub][1][c] = v1
                sep[base_sub + c] = v0 << shift
                sep[base_sub + 4 + c] = v1 << shift
            if pk == 1:
                pb[sub][0] = val[sub][0][0] & 1
                pb[sub][1] = val[sub][1][0] & 1
            elif pk == 2:
                p0 = val[sub][0][0] & 1
                pb[sub][0] = p0
                pb[sub][1] = p0
                if (val[sub][1][0] & 1) != p0:
                    st |= _B7_PBIT
        for sub in range(ns, 3):
            sep[sub * 8:sub * 8 + 8] = sep[0:8]
        eps[i] = sep

        b1 = _B7_IB[mode]
        b1_shift = 4 - b1
        b1_mask = (1 << b1) - 1
        two = mode in (4, 5)
        s1 = [0] * 16
        s2 = [0] * 16 if two else None
        six = [0] * 32
        for y in range(4):
            r1 = rows1[y]
            sa, sb = r1[a], r1[b]
            row = y * 4
            if y < 3:
                d0, d1, d2, d3 = deint1[sa], deint0[sa], deint1[sb], deint0[sb]
            else:
                d0, d1, d2, d3 = deint0[sa], deint1[sa], deint0[sb], deint1[sb]
            for off, dv in ((0, d0), (1, d1), (2, d2), (3, d3)):
                p = row + off
                iv = ((rix[p] >> b1_shift) + _unzig(dv)) & b1_mask
                s1[p] = iv
                six[p] = iv << b1_shift
            if two:
                r2 = rows2[y]
                s2a, s2b = r2[a], r2[b]
                if y < 3:
                    e0, e1, e2, e3 = deint1[s2a], deint0[s2a], deint1[s2b], deint0[s2b]
                else:
                    e0, e1, e2, e3 = deint0[s2a], deint1[s2a], deint0[s2b], deint1[s2b]
                for off, dv in ((0, e0), (1, e1), (2, e2), (3, e3)):
                    p = row + off
                    iv2 = ((rix[16 + p] >> 2) + _unzig(dv)) & 3
                    s2[p] = iv2
                    six[16 + p] = iv2 << 2
        ixs[i] = six

        if mode == 0 and part == 0 and not any(sep) and not any(s1):
            status[i] = st
            continue

        sm = p2[part] if ns == 2 else (p3[part] if ns == 3 else None)
        anchors = (0,) if ns == 1 else ((0, a2[part]) if ns == 2 else (0, a3a[part], a3b[part]))
        if mode == 4:
            pri, ib, sec, ib2 = s2, 2, s1, 3
        elif mode == 5:
            pri, ib, sec, ib2 = s1, 2, s2, 2
        else:
            pri, ib, sec, ib2 = s1, b1, None, 0

        acc = 1 << mode
        pos = mode + 1
        pbits = _B7_PB[mode]
        if pbits:
            acc |= (part & ((1 << pbits) - 1)) << pos
            pos += pbits
        if mode in (4, 5):
            acc |= (rot & 3) << pos
            pos += 2
        if mode == 4:
            acc |= (isel & 1) << pos
            pos += 1
        cb_mask = (1 << cb) - 1
        for c in range(3):
            tc = 3 if (rot and c == rot - 1) else c
            drop = bool(pk and tc == 0)
            for sub in range(ns):
                for e in range(2):
                    v = val[sub][e][tc]
                    acc |= ((v >> 1 if drop else v) & cb_mask) << pos
                    pos += cb
        if ab:
            ab_mask = (1 << ab) - 1
            tc = rot - 1 if rot else 3
            drop = bool(pk and tc == 0)
            for sub in range(ns):
                for e in range(2):
                    v = val[sub][e][tc]
                    acc |= ((v >> 1 if drop else v) & ab_mask) << pos
                    pos += ab
        if pk == 1:
            for sub in range(ns):
                acc |= (pb[sub][0] & 1) << pos
                pos += 1
                acc |= (pb[sub][1] & 1) << pos
                pos += 1
        elif pk == 2:
            for sub in range(ns):
                acc |= (pb[sub][0] & 1) << pos
                pos += 1

        ib_mask = (1 << ib) - 1
        ib_amask = (1 << (ib - 1)) - 1
        for p in range(16):
            anchor = p == anchors[sm[p] if sm is not None else 0]
            pv = pri[p]
            if anchor:
                if pv >> (ib - 1):
                    st |= _B7_ANCHOR
                acc |= (pv & ib_amask) << pos
                pos += ib - 1
            else:
                acc |= (pv & ib_mask) << pos
                pos += ib
        if sec is not None:
            ib2_mask = (1 << ib2) - 1
            ib2_amask = (1 << (ib2 - 1)) - 1
            for p in range(16):
                sv = sec[p]
                if p == 0:
                    if sv >> (ib2 - 1):
                        st |= _B7_ANCHOR
                    acc |= (sv & ib2_amask) << pos
                    pos += ib2 - 1
                else:
                    acc |= (sv & ib2_mask) << pos
                    pos += ib2
        if pos != 128:
            st |= _B7_SIGNATURE
        out[16 * i:16 * i + 16] = acc.to_bytes(16, "little")
        status[i] = st
    return bytes(out), status


def _bc7_blocks(lanes, nblocks, provisional, *, history=None):
    """Rebuild `nblocks` 16-byte BC7 blocks from the 16 BCPack lanes."""
    if len(lanes[0]) != 2 * nblocks:
        raise BcpackError("BC7 lane length does not match the block count")
    table = _bptc.load_bc7(history)
    unknown = _bc7_check(lanes, nblocks, table, provisional, has_history=(history is not None))
    if unknown:
        l0, l1 = lanes[0], lanes[1]
        er = [0] * nblocks
        ir = [0] * nblocks
        for i in range(nblocks):
            di = _inter8(l1[2 * i], l1[2 * i + 1])
            de = (di + _unzig(_inter8(l0[2 * i], l0[2 * i + 1]))) & 255
            er[i] = -1 if de == 0 else (256 + i - de if de > i else er[i - de])
            ir[i] = -1 if di == 0 else (256 + i - di if di > i else ir[i - di])
        counts = [(kinds, k, (er if kinds == "endpoint" else ir).count(k)) for kinds, k in unknown]
        total = sum(c for _, _, c in counts)
        if total > _loose_limit(nblocks):
            names = ", ".join(f"{kinds} {k}" for kinds, k, _ in counts[:6])
            if len(counts) > 6:
                names += ", ..."
            hint = " (pass --history <path>)" if history is None else ""
            raise BcpackProvisionalError(
                f"BC7 chunk has {total}/{nblocks} blocks from unknown built-in history entries ({names}){hint}"
            )
        for kinds, k, count in counts:
            provisional.add(f"BC7 unknown {kinds} history {k} ({count} blocks)")
    data, status = _bc7_rebuild(lanes, nblocks, table)
    bad = [i for i, st in enumerate(status) if st]
    if bad:
        first_st = status[bad[0]]
        if not (first_st & (_B7_ANCHOR | _B7_PBIT)):
            raise BcpackError(
                f"BC7 chunk failed signature check ({len(bad)}/{nblocks} blocks; first: block {bad[0]})"
            )
        if provisional is None or not provisional:
            raise BcpackError(
                f"BC7 chunk failed anchor/p-bit consistency check "
                f"({len(bad)}/{nblocks} blocks; first: block {bad[0]})"
            )
        if len(bad) > _loose_limit(nblocks):
            raise BcpackProvisionalError(
                f"BC7 chunk failed anchor/p-bit consistency check in {len(bad)}/{nblocks} blocks"
            )
        provisional.add(f"BC7 consistency check failed in {len(bad)} blocks")
    return data


_REBUILDERS = {
    1: _bc1_blocks,
    3: _bc3_blocks,
    4: _bc4_blocks,
    5: _bc5_blocks,
    6: _bc6h_blocks,
    7: _bc7_blocks,
}


def decode_with_info(raw, codec, out_size, *, allow_provisional=False, history=None):
    """Decode one BCPack chunk, returning `(decoded_bytes, provisional_labels)`.

    When `allow_provisional` is False (strict mode), any unconfirmed or unknown
    built-in history reference raises `BcpackProvisionalError` and the returned
    set is always empty. For BC6H (`codec 6`) and BC7 (`codec 7`), `history`
    may point to a locally generated JSON file, directory, or dict supplying
    the built-in initial history tables.
    """
    rebuilder = _REBUILDERS.get(codec)
    if rebuilder is None:
        name = CODEC_NAMES.get(codec, str(codec))
        raise BcpackUnsupportedCodec(f"BCPack block rebuilder for codec {codec} ({name}) is not implemented yet")
    lanes, _ = decode_lanes(raw, codec, out_size)
    nblocks = out_size // BLOCK_BYTES[codec]
    prov = set() if allow_provisional else None
    if codec in (6, 7):
        data = rebuilder(lanes, nblocks, prov, history=history)
    else:
        data = rebuilder(lanes, nblocks, prov)
    return data, (prov if prov is not None else set())


def decode(raw, codec, out_size, *, allow_provisional=False, history=None):
    """Decode one BCPack chunk into `out_size` bytes of standard BCn blocks."""
    data, _ = decode_with_info(
        raw, codec, out_size, allow_provisional=allow_provisional, history=history
    )
    return data
````

## tools/tex_headers.py

SHA-256 `7a2c87af0461adadfcb98d4e28bb5daa67e8231bc1c8813fd551dc9be562cc0b`

````python
"""Find texture headers in carved CPU-segment blobs and pair them with their GPU blob.

Texture descriptor layout (qwords, found in GTA VI's resource CPU segments):
  q[k-2]  packed u64 (unknown: size/flags)
  q[k-1]  0x980                     (descriptor type)
  q[k]    0x60000000 + offset       (GPU data pointer into the resource's GPU segment)
  q[k+4]  u16 width, u16 height, u16 depth/array, u8 ?, u8 DXGI format
  q[k+5]  tiling / flags (0x0001 = AMD SW_4K_S verified on an R16 texture)
The GPU segment is the carved blob that follows the CPU blob.

This module also carries the Gfx10 compact mip layout rule used by the RDS5/TTPF pools
(`tools/ttpf_mips.py`): tile-mode selection, the packed tail, and the allocation-span check.

Usage:
    python -I tex_headers.py <carve dir> [--archives a,b] [--out textures_index.json]
"""
import argparse
import array
import json
import os
import struct
import sys
from collections import Counter

_UINT64_CODE = "Q" if array.array("Q").itemsize == 8 else None

DXGI = {
    2: "R32G32B32A32_FLOAT", 3: "R32G32B32A32_UINT", 4: "R32G32B32A32_SINT",
    6: "R32G32B32_FLOAT", 7: "R32G32B32_UINT", 8: "R32G32B32_SINT",
    10: "R16G16B16A16_FLOAT", 11: "R16G16B16A16_UNORM", 12: "R16G16B16A16_UINT",
    13: "R16G16B16A16_SNORM", 14: "R16G16B16A16_SINT",
    16: "R32G32_FLOAT", 17: "R32G32_UINT", 18: "R32G32_SINT",
    24: "R10G10B10A2_UNORM", 25: "R10G10B10A2_UINT", 26: "R11G11B10_FLOAT",
    28: "R8G8B8A8_UNORM", 29: "R8G8B8A8_UNORM_SRGB", 30: "R8G8B8A8_UINT",
    31: "R8G8B8A8_SNORM", 32: "R8G8B8A8_SINT",
    34: "R16G16_FLOAT", 35: "R16G16_UNORM", 36: "R16G16_UINT",
    37: "R16G16_SNORM", 38: "R16G16_SINT",
    41: "R32_FLOAT", 42: "R32_UINT", 43: "R32_SINT",
    49: "R8G8_UNORM", 50: "R8G8_UINT", 51: "R8G8_SNORM", 52: "R8G8_SINT",
    54: "R16_FLOAT", 56: "R16_UNORM", 57: "R16_UINT", 58: "R16_SNORM", 59: "R16_SINT",
    61: "R8_UNORM", 62: "R8_UINT", 63: "R8_SNORM", 64: "R8_SINT",
    71: "BC1_UNORM", 72: "BC1_UNORM_SRGB",
    74: "BC2_UNORM", 75: "BC2_UNORM_SRGB",
    77: "BC3_UNORM", 78: "BC3_UNORM_SRGB",
    80: "BC4_UNORM", 81: "BC4_SNORM",
    83: "BC5_UNORM", 84: "BC5_SNORM",
    87: "B8G8R8A8_UNORM", 91: "B8G8R8A8_UNORM_SRGB",
    95: "BC6H_UF16", 96: "BC6H_SF16",
    98: "BC7_UNORM", 99: "BC7_UNORM_SRGB",
}

GFX10_TO_DXGI = {
    1: 61,
    2: 63,
    5: 62,
    6: 64,
    7: 56,
    8: 58,
    11: 57,
    12: 59,
    13: 54,
    14: 49,
    15: 51,
    18: 50,
    19: 52,
    20: 42,
    21: 43,
    22: 41,
    23: 35,
    24: 37,
    27: 36,
    28: 38,
    29: 34,
    43: 26,
    44: 24,
    48: 25,
    56: 28,
    57: 31,
    60: 30,
    61: 32,
    62: 17,
    63: 18,
    64: 16,
    65: 11,
    66: 13,
    69: 12,
    70: 14,
    71: 10,
    72: 7,
    73: 8,
    74: 6,
    75: 3,
    76: 4,
    77: 2,
    130: 29,
    169: 71,
    170: 72,
    171: 74,
    172: 75,
    173: 77,
    174: 78,
    175: 80,
    176: 81,
    177: 83,
    178: 84,
    179: 95,
    180: 96,
    181: 98,
    182: 99,
}
DXGI_TO_GFX10 = {v: k for k, v in GFX10_TO_DXGI.items()}


def map_gfx10_format(gfx10_code):
    if gfx10_code not in GFX10_TO_DXGI:
        raise ValueError(f"unsupported or invalid GFX10 format: {gfx10_code}")
    dxgi_id = GFX10_TO_DXGI[gfx10_code]
    return dxgi_id, DXGI.get(dxgi_id, f"dxgi{dxgi_id}")


def dxgi_to_gfx10(dxgi_code):
    if dxgi_code not in DXGI_TO_GFX10:
        raise ValueError(f"unsupported DXGI format: {dxgi_code}")
    return DXGI_TO_GFX10[dxgi_code]


def calc_mipmap_count(w, h, depth=1):
    if w <= 0 or h <= 0 or depth <= 0:
        return 0
    return max(w, h, depth).bit_length()


def calc_mipmap_dimensions(w, h, depth=1, mips=0):
    if w <= 0 or h <= 0 or depth <= 0:
        return []
    max_mips = calc_mipmap_count(w, h, depth)
    count = max_mips if mips <= 0 else min(mips, max_mips)
    return [(max(1, w >> i), max(1, h >> i), max(1, depth >> i)) for i in range(count)]


FMT_INFO = {
    71: (8, 4), 72: (8, 4), 80: (8, 4), 81: (8, 4),
    74: (16, 4), 75: (16, 4), 77: (16, 4), 78: (16, 4), 83: (16, 4), 84: (16, 4),
    95: (16, 4), 96: (16, 4), 98: (16, 4), 99: (16, 4),
    61: (1, 1), 62: (1, 1), 63: (1, 1), 64: (1, 1),
    49: (2, 1), 50: (2, 1), 51: (2, 1), 52: (2, 1), 54: (2, 1), 56: (2, 1), 57: (2, 1), 58: (2, 1), 59: (2, 1),
    16: (8, 1), 17: (8, 1), 18: (8, 1),
    24: (4, 1), 25: (4, 1), 26: (4, 1), 28: (4, 1), 29: (4, 1), 30: (4, 1), 31: (4, 1), 32: (4, 1),
    34: (4, 1), 35: (4, 1), 36: (4, 1), 37: (4, 1), 38: (4, 1), 41: (4, 1), 42: (4, 1), 43: (4, 1),
    87: (4, 1), 91: (4, 1),
    6: (12, 1), 7: (12, 1), 8: (12, 1),
    10: (8, 1), 11: (8, 1), 12: (8, 1), 13: (8, 1), 14: (8, 1),
    2: (16, 1), 3: (16, 1), 4: (16, 1),
}


def calc_mip_level_bytes(w, h, depth=1, fmt=28, align=1):
    if fmt not in FMT_INFO:
        raise ValueError(f"unsupported format for byte calculation: {fmt}")
    bpe, blk = FMT_INFO[fmt]
    we = max(1, (w + blk - 1) // blk)
    he = max(1, (h + blk - 1) // blk)
    slice_bytes = we * he * bpe
    total = slice_bytes * max(1, depth)
    if align > 1:
        total = (total + align - 1) // align * align
    return total


# AMD Gfx10 compact mip chain (the TTPF "compact" profile) and multi-slice layouts.
#
# The 9-bit descriptor mode is a low flag bit plus a 4-bit Gfx10 tile mode at
# bit 1. Tile mode 0 is SW_64KB_D; the observed 1-3 and 9-12 values are
# SW_4KB_S. Mips are stored smallest first. The last few mips share one tile at
# offset 0 instead of getting their own allocation.
COMPACT_TILE_4K = 4096
COMPACT_TILE_64K = 65536
COMPACT_MAX_TAIL_MIPS = {COMPACT_TILE_4K: 8, COMPACT_TILE_64K: 12}
_COMPACT_ELEMENT_LOG = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}
_COMPACT_TILE_ORIGIN = {0: (16, 16), 1: (16, 8), 2: (8, 8), 3: (8, 4), 4: (4, 4)}
# AMD Gfx10 3D SW_4KB_S micro-tile extents (blocks_w, blocks_h, blocks_d) by log2(element_bytes).
_VOLUME_4K_TILE = {
    0: (16, 16, 16),
    1: (16, 8, 16),
    2: (8, 8, 16),
    3: (8, 8, 8),
    4: (8, 4, 8),
}
# 5-bit chunk page-count codes packed in the low 20 bits of ((extra << 11) | meta),
# mapping each non-zero code to its RDS5 chunk virtual size in 4 KiB pages.
ETPF_CHUNK_CODE_PAGES = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
    10: 12, 11: 16, 12: 24, 13: 32, 14: 48, 15: 64, 16: 128,
    21: 18, 22: 80, 23: 96, 24: 144, 26: 272, 27: 384, 28: 528,
}


def gfx10_tile_mode(mode):
    """Return the 4-bit Gfx10 tile mode hidden in the TTPF descriptor mode."""
    if not isinstance(mode, int) or mode < 0:
        raise ValueError(f"invalid descriptor mode: {mode!r}")
    return (mode >> 1) & 0xF


def gfx10_tile_bytes(mode):
    """Tile size for a descriptor mode: 64 KiB only for tile mode 0."""
    return COMPACT_TILE_64K if gfx10_tile_mode(mode) == 0 else COMPACT_TILE_4K


def parse_etpf_texture_record(record):
    """Parse one 16-byte ETPF texture record (the RDS5 embedded descriptor).

    Word ``b`` packs 3-bit ``non_tail`` (bits 0..2), 7-bit DXGI ``format``
    (bits 3..9), 11-bit ``depth - 1`` (bits 10..20), 2-bit ``dimension``
    (bits 21..22), and 9-bit ``mode`` (bits 23..31).
    """
    if len(record) < 16:
        raise ValueError(f"ETPF texture record truncated: expected 16 bytes, got {len(record)}")
    a, b, c, d = struct.unpack_from("<IIII", record, 0)
    return {
        "width": (a & 0x3FFF) + 1,
        "height": ((a >> 14) & 0x3FFF) + 1,
        "packed_mips": a >> 28,
        "non_tail": b & 7,
        "mips": (a >> 28) + (b & 7),
        "format": (b >> 3) & 0x7F,
        "depth": ((b >> 10) & 0x7FF) + 1,
        "dimension": (b >> 21) & 3,
        "mode": b >> 23,
        "meta": c >> 21,
        "extra": d,
        "base": (c & 0x1FFFFF) * 4096,
    }


def decode_etpf_chunk_pages(meta, extra):
    """Decode the 43-bit ``(extra << 11) | meta`` streaming chunk-page list.

    The low 20 bits hold up to four zero-terminated 5-bit codes giving each
    RDS5 chunk's virtual size in 4 KiB pages. Bits 9..18 of ``extra`` must be
    zero. Returns a tuple of page counts, or ``None`` if any code or reserved
    bit is invalid.
    """
    if not isinstance(meta, int) or not isinstance(extra, int):
        return None
    if meta < 0 or meta > 0x7FF or extra < 0 or extra > 0xFFFFFFFF:
        return None
    if ((extra >> 9) & 0x3FF) != 0:
        return None
    val43 = (extra << 11) | meta
    pages = []
    ended = False
    for slot in range(4):
        code = (val43 >> (5 * slot)) & 0x1F
        if code == 0:
            ended = True
            continue
        if ended:
            return None
        count = ETPF_CHUNK_CODE_PAGES.get(code)
        if count is None:
            return None
        pages.append(count)
    return tuple(pages)


def etpf_streaming_padding(extra):
    """Return ``(align_group, pad_pages)`` from the upper 13 bits of ``extra``."""
    return (extra >> 19) & 3, extra >> 21


def compact_profile_key(descriptor, element_bytes):
    """The exact tuple a validated compact-profile table is keyed on."""
    return (descriptor["mode"], descriptor["width"], descriptor["height"],
            descriptor["mips"], descriptor["non_tail"], element_bytes)


def compact_surface_layout(width, height, mips, element_bytes, block=1,
                           tile=COMPACT_TILE_4K):
    """Compute the Gfx10 compact mip chain for one 2D texture.

    ``element_bytes`` is the size of one pixel or BC block; ``block`` is 4 for
    BC formats and 1 for uncompressed formats. Returns the allocation size,
    the first packed-tail mip, block tile dimensions and one entry per mip
    with its offset and region size. Raises ValueError for a mip count that
    cannot describe the surface or a tile/element size outside the measured
    set.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid surface dimensions {width}x{height}")
    if element_bytes not in _COMPACT_ELEMENT_LOG:
        raise ValueError(f"unsupported element size: {element_bytes}")
    if block not in (1, 4):
        raise ValueError(f"unsupported block dimension: {block}")
    if tile not in COMPACT_MAX_TAIL_MIPS:
        raise ValueError(f"unsupported compact tile size: {tile}")
    levels = max(width, height).bit_length()
    if mips < 1 or mips > levels:
        raise ValueError(f"invalid mip count {mips} for {width}x{height}")

    log = _COMPACT_ELEMENT_LOG[element_bytes]
    half_bits = 6 if tile == COMPACT_TILE_4K else 8
    max_tail = COMPACT_MAX_TAIL_MIPS[tile]
    bw = 1 << (half_bits - log // 2)
    bh = 1 << (half_bits - (log + 1) // 2)
    mw, mh = _COMPACT_TILE_ORIGIN[log]
    ew = (width + block - 1) // block
    eh = (height + block - 1) // block

    tail = mips
    sizes = []
    out = []
    for i in range(mips):
        wc = max(1, (ew + (1 << i) - 1) >> i)
        hc = max(1, (eh + (1 << i) - 1) >> i)
        if mips > 1 and wc <= bw // 2 and hc <= bh and mips - i <= max_tail:
            tail = i
            break
        pw = (wc + bw - 1) // bw * bw
        ph = (hc + bh - 1) // bh * bh
        sizes.append(pw * ph * element_bytes)
        out.append({
            "index": i, "blocks_w": wc, "blocks_h": hc, "padded_w": pw, "padded_h": ph,
            "pixels_w": max(1, width >> i), "pixels_h": max(1, height >> i),
            "offset": 0, "region": pw * ph * element_bytes, "tile_x": 0, "tile_y": 0,
            "in_tail": False,
        })

    off = tile if tail < mips else 0
    for i in range(tail - 1, -1, -1):
        out[i]["offset"] = off
        off += sizes[i]
    for i in range(tail, mips):
        entry = max_tail - 1 - (i - tail)
        moff = (16 << entry) if entry > 6 else entry << 8
        x = y = 0
        for bit in range(6):
            x |= ((moff >> (9 + 2 * bit)) & 1) << bit
            y |= ((moff >> (8 + 2 * bit)) & 1) << bit
        wc = max(1, (ew + (1 << i) - 1) >> i)
        hc = max(1, (eh + (1 << i) - 1) >> i)
        out.append({
            "index": i, "blocks_w": wc, "blocks_h": hc, "padded_w": bw, "padded_h": bh,
            "pixels_w": max(1, width >> i), "pixels_h": max(1, height >> i),
            "offset": 0, "region": tile, "tile_x": x * mw, "tile_y": y * mh,
            "in_tail": True, "tail_offset": moff,
        })
    return {
        "size": off, "tile": tile, "first_tail": tail, "block_w": bw, "block_h": bh,
        "element_bytes": element_bytes, "levels": levels, "mips": out,
    }


def compact_layout_for_dxgi(width, height, fmt, mips, tile=COMPACT_TILE_4K):
    """Compact layout using tex_headers' DXGI element-size table."""
    if fmt not in FMT_INFO:
        raise ValueError(f"unsupported format for compact layout: {fmt}")
    bpe, blk = FMT_INFO[fmt]
    return compact_surface_layout(width, height, mips, bpe, blk, tile)


def array_surface_layout(width, height, depth, mips, element_bytes, block=1,
                         tile=COMPACT_TILE_64K):
    """Compute the mip-major Gfx10 layout for a 2D texture array.

    Every slice shares the same per-mip dimensions; the packed tail (if any)
    occupies ``depth * tile`` bytes at offset 0 (slice ``s`` at ``s * tile``),
    followed by standalone mips from ``first_tail - 1`` down to ``0``, each
    occupying ``depth * region`` bytes (slice ``s`` at ``offset + s * region``).
    """
    if not isinstance(depth, int) or depth < 1:
        raise ValueError(f"invalid array depth: {depth!r}")
    base = compact_surface_layout(width, height, mips, element_bytes, block, tile)
    first_tail = base["first_tail"]
    mips_out = [dict(m) for m in base["mips"]]
    off = depth * tile if first_tail < mips else 0
    for i in range(first_tail - 1, -1, -1):
        mips_out[i]["offset"] = off
        mips_out[i]["slice_stride"] = mips_out[i]["region"]
        off += depth * mips_out[i]["region"]
    for i in range(first_tail, mips):
        mips_out[i]["offset"] = 0
        mips_out[i]["slice_stride"] = tile
    return {
        "size": off,
        "slice_size": base["size"],
        "tile": tile,
        "first_tail": first_tail,
        "block_w": base["block_w"],
        "block_h": base["block_h"],
        "element_bytes": element_bytes,
        "levels": base["levels"],
        "depth": depth,
        "mip_major": True,
        "mips": mips_out,
    }


def array_layout_for_dxgi(width, height, depth, fmt, mips, tile=COMPACT_TILE_64K):
    """Mip-major 2D array layout using tex_headers' DXGI element-size table."""
    if fmt not in FMT_INFO:
        raise ValueError(f"unsupported format for array layout: {fmt}")
    bpe, blk = FMT_INFO[fmt]
    return array_surface_layout(width, height, depth, mips, bpe, blk, tile)


def cubemap_surface_layout(width, height, mips, element_bytes, block=1,
                           non_tail=0, chunk_pages=None):
    """Compute the slice-major SW_4KB_S layout for a 6-face streaming cubemap.

    ``non_tail == 0`` (mode 18) stores one 6-face cubemap at offset 0.
    ``non_tail in 1..3`` (modes 20/22/24) stores ``non_tail + 1`` self-contained
    cubemap snapshots back-to-back in the RDS5 chunk stream; the final chunk
    holds the full-resolution 6-face slice-major cubemap, zero-padded to a
    64 KiB boundary when ``6 * face_size >= 36 * 4096``.
    """
    if not isinstance(non_tail, int) or not 0 <= non_tail <= 3:
        raise ValueError(f"unsupported cubemap non_tail: {non_tail!r}")
    face = compact_surface_layout(width, height, mips, element_bytes, block, COMPACT_TILE_4K)
    face_size = face["size"]
    full_bytes = 6 * face_size
    if non_tail == 0:
        padded_full = full_bytes
        if chunk_pages is not None and len(chunk_pages) != 0:
            if len(chunk_pages) != 1 or chunk_pages[0] * COMPACT_TILE_4K != padded_full:
                raise ValueError(
                    f"non-streaming cubemap chunk_pages {chunk_pages!r} != expected ({padded_full // COMPACT_TILE_4K},)")
        data_offset = 0
        total_size = full_bytes
    else:
        padded_full = ((full_bytes + 65535) // 65536 * 65536
                       if full_bytes >= 36 * COMPACT_TILE_4K else full_bytes)
        if chunk_pages is not None:
            if len(chunk_pages) != non_tail + 1:
                raise ValueError(
                    f"cubemap chunk count mismatch: expected {non_tail + 1}, got {len(chunk_pages)}")
            if chunk_pages[-1] * COMPACT_TILE_4K != padded_full:
                raise ValueError(
                    f"cubemap final chunk size {chunk_pages[-1] * COMPACT_TILE_4K} != expected {padded_full}")
            data_offset = sum(chunk_pages[:-1]) * COMPACT_TILE_4K
            total_size = sum(chunk_pages) * COMPACT_TILE_4K
        else:
            data_offset = 0
            total_size = padded_full
    return {
        "size": total_size,
        "data_offset": data_offset,
        "face_size": face_size,
        "full_bytes": full_bytes,
        "padded_full_bytes": padded_full,
        "snapshots": non_tail + 1,
        "tile": COMPACT_TILE_4K,
        "first_tail": face["first_tail"],
        "block_w": face["block_w"],
        "block_h": face["block_h"],
        "element_bytes": element_bytes,
        "levels": face["levels"],
        "depth": 6,
        "mips": face["mips"],
    }


def cubemap_layout_for_dxgi(width, height, fmt, mips, non_tail=0, chunk_pages=None):
    """Cubemap layout using tex_headers' DXGI element-size table."""
    if fmt not in FMT_INFO:
        raise ValueError(f"unsupported format for cubemap layout: {fmt}")
    bpe, blk = FMT_INFO[fmt]
    return cubemap_surface_layout(width, height, mips, bpe, blk, non_tail, chunk_pages)


def volume_surface_layout(width, height, depth, mips, element_bytes):
    """Compute the AMD Gfx10 3D SW_4KB_S layout for a single-mip volume texture."""
    if width <= 0 or height <= 0 or depth <= 0:
        raise ValueError(f"invalid volume dimensions {width}x{height}x{depth}")
    if mips != 1:
        raise ValueError(f"only single-mip 3D volumes are validated, got mips={mips}")
    if element_bytes not in _COMPACT_ELEMENT_LOG:
        raise ValueError(f"unsupported volume element size: {element_bytes}")
    bw, bh, bd = _VOLUME_4K_TILE[_COMPACT_ELEMENT_LOG[element_bytes]]
    pw = (width + bw - 1) // bw * bw
    ph = (height + bh - 1) // bh * bh
    pd = (depth + bd - 1) // bd * bd
    z_tile_stride = (pw // bw) * (ph // bh) * COMPACT_TILE_4K
    size = (pd // bd) * z_tile_stride
    return {
        "size": size,
        "tile": COMPACT_TILE_4K,
        "first_tail": 1,
        "block_w": bw,
        "block_h": bh,
        "block_d": bd,
        "padded_w": pw,
        "padded_h": ph,
        "padded_d": pd,
        "z_tile_stride": z_tile_stride,
        "element_bytes": element_bytes,
        "depth": depth,
        "levels": calc_mipmap_count(width, height, depth),
        "mips": [{
            "index": 0,
            "blocks_w": width,
            "blocks_h": height,
            "blocks_d": depth,
            "padded_w": pw,
            "padded_h": ph,
            "padded_d": pd,
            "pixels_w": width,
            "pixels_h": height,
            "pixels_d": depth,
            "offset": 0,
            "region": size,
            "tile_x": 0,
            "tile_y": 0,
            "in_tail": False,
        }],
    }


def volume_layout_for_dxgi(width, height, depth, fmt, mips=1):
    """Single-mip 3D SW_4KB_S volume layout using tex_headers' DXGI table."""
    if fmt not in FMT_INFO:
        raise ValueError(f"unsupported format for volume layout: {fmt}")
    bpe, blk = FMT_INFO[fmt]
    if blk != 1:
        raise ValueError(f"block-compressed 3D volumes are not supported: format {fmt}")
    return volume_surface_layout(width, height, depth, mips, bpe)


def compact_span_matches(layout, span):
    """True only when an allocation span is byte-exact for the computed chain."""
    return isinstance(span, int) and span == layout["size"]


DDSD_CAPS = 0x00000001
DDSD_HEIGHT = 0x00000002
DDSD_WIDTH = 0x00000004
DDSD_PITCH = 0x00000008
DDSD_PIXELFORMAT = 0x00001000
DDSD_MIPMAPCOUNT = 0x00020000
DDSD_LINEARSIZE = 0x00080000
DDSD_DEPTH = 0x00800000

DDSCAPS_COMPLEX = 0x00000008
DDSCAPS_MIPMAP = 0x00400000
DDSCAPS_TEXTURE = 0x00001000

DDSCAPS2_CUBEMAP = 0x00000200
DDSCAPS2_CUBEMAP_ALLFACES = 0x0000FE00
DDSCAPS2_VOLUME = 0x00200000

D3D10_RESOURCE_DIMENSION_TEXTURE2D = 3
D3D10_RESOURCE_DIMENSION_TEXTURE3D = 4
D3D10_RESOURCE_MISC_TEXTURECUBE = 0x4


def dds_header(w, h, depth=1, mips=1, fmt=28, is_cube=False, linear_size=0, array_size=1):
    """Build a DX10 DDS header; array_size counts cubes, not faces, for cubemaps."""
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT
    if mips > 1:
        flags |= DDSD_MIPMAPCOUNT
    if depth > 1:
        flags |= DDSD_DEPTH
    if linear_size > 0:
        flags |= DDSD_LINEARSIZE
    else:
        flags |= 0x80000

    caps = DDSCAPS_TEXTURE
    if mips > 1:
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    if depth > 1 or is_cube or array_size > 1:
        caps |= DDSCAPS_COMPLEX

    caps2 = 0
    if depth > 1:
        caps2 |= DDSCAPS2_VOLUME
    if is_cube:
        caps2 |= DDSCAPS2_CUBEMAP_ALLFACES

    struct.pack_into("<IIIIIII", hdr, 4, 124, flags, h, w, linear_size, depth if depth > 1 else 0, mips if mips > 1 else 1)
    struct.pack_into("<II4s", hdr, 76, 32, 4, b"DX10")
    struct.pack_into("<II", hdr, 108, caps, caps2)

    dim = D3D10_RESOURCE_DIMENSION_TEXTURE3D if depth > 1 else D3D10_RESOURCE_DIMENSION_TEXTURE2D
    misc = D3D10_RESOURCE_MISC_TEXTURECUBE if is_cube else 0
    dxt10 = struct.pack("<IIIII", fmt, dim, misc, array_size, 0)
    return bytes(hdr) + dxt10


def dds_bytes(w, h, fmt, payload=b"", mips=1, depth=1, is_cube=False, array_size=1):
    return dds_header(w, h, depth=depth, mips=mips, fmt=fmt, is_cube=is_cube,
                      linear_size=len(payload), array_size=array_size) + payload


def parse_dds_header(data):
    if len(data) < 128:
        raise ValueError(f"DDS header truncated: expected at least 128 bytes, got {len(data)}")
    if data[:4] != b"DDS ":
        raise ValueError(f"invalid DDS magic: {data[:4]!r}")
    size, flags, h, w, pitch_linear, depth, mips = struct.unpack_from("<IIIIIII", data, 4)
    if size != 124:
        raise ValueError(f"invalid DDS header size: {size}")
    pf_size, pf_flags, fourcc = struct.unpack_from("<II4s", data, 76)
    if pf_size != 32:
        raise ValueError(f"invalid DDS pixel format size: {pf_size}")
    caps, caps2 = struct.unpack_from("<II", data, 108)

    info = {
        "magic": b"DDS ",
        "flags": flags,
        "width": w,
        "height": h,
        "depth": depth,
        "mips": mips,
        "pitch_linear": pitch_linear,
        "fourcc": fourcc,
        "caps": caps,
        "caps2": caps2,
    }

    if fourcc == b"DX10":
        if len(data) < 148:
            raise ValueError(f"truncated DX10 extension header: expected at least 148 bytes, got {len(data)}")
        dxgi_fmt, dim, misc, array_size, misc2 = struct.unpack_from("<IIIII", data, 128)
        info.update({
            "dxgi_format": dxgi_fmt,
            "resource_dimension": dim,
            "misc_flags": misc,
            "array_size": array_size,
            "misc_flags2": misc2,
        })
    return info


def _find_gpu_ptr_qwords_stdlib(buf: bytes):
    """Return (qwords, hit_indices) for 64-bit GPU pointers matching 0x60000000..0x6FFFFFFF."""
    n_qwords = len(buf) // 8
    if n_qwords == 0:
        return (), []
    trimmed = memoryview(buf)[: n_qwords * 8]
    if _UINT64_CODE is not None:
        q = array.array(_UINT64_CODE)
        q.frombytes(trimmed)
        if sys.byteorder != "little":
            q.byteswap()
    else:
        q = struct.unpack(f"<{n_qwords}Q", trimmed)
    hits = [k for k, v in enumerate(q) if 0x60000000 <= v <= 0x6FFFFFFF]
    return q, hits


def _find_gpu_ptr_qwords(buf: bytes):
    """Scan aligned little-endian u64 qwords, using numpy when installed or stdlib fallback."""
    try:
        import numpy as np
    except ImportError:
        return _find_gpu_ptr_qwords_stdlib(buf)
    q = np.frombuffer(buf[: len(buf) // 8 * 8], "<u8")
    hits = np.nonzero(((q >> 28) == 6) & ((q >> 32) == 0))[0]
    return q, hits


def scan_archive(carve, arch):
    with open(os.path.join(carve, arch, "index.json"), encoding="utf-8") as f:
        files = sorted(json.load(f)["files"], key=lambda r: r["off"])
    out = []
    for i in range(len(files) - 1):
        v, g = files[i], files[i + 1]
        # CPU segment: starts with a zero qword but isn't zero-padded GPU data. The GPU segment is whatever
        # blob follows it (texture data often starts directly with BC blocks, not a zero header).
        if not (v["head"][:16] == "0" * 16 and not v["head"].startswith("0" * 32)):
            continue
        if g["head"].startswith("42400000") or g.get("type") == "bink2":
            continue
        # The GPU segment can span several consecutive blobs: everything up to the next CPU/header blob.
        chain = []
        for j in range(i + 1, min(len(files), i + 257)):
            r = files[j]
            if r["head"].startswith("42400000") or r.get("type") == "bink2" or (
                    r["head"][:16] == "0" * 16 and not r["head"].startswith("0" * 32) and chain):
                break
            chain.append([r["off"], r["size"]])
        with open(os.path.join(carve, arch, f"{v['off']:012x}.bin"), "rb") as f:
            V = f.read()
        q, hits = _find_gpu_ptr_qwords(V)
        # Any GPU pointer whose header (4 qwords later) decodes to sane dimensions and a known DXGI format.
        for k in hits:
            k = int(k)
            if k < 2 or k + 5 >= len(q):
                continue
            d = int(q[k + 4]).to_bytes(8, "little")
            w, h, depth = int.from_bytes(d[0:2], "little"), int.from_bytes(d[2:4], "little"), int.from_bytes(d[4:6], "little")
            fmt = d[7]
            if fmt not in DXGI or not (4 <= w <= 16384 and 4 <= h <= 16384 and 1 <= depth <= 2048):
                continue
            # Real texture data is 256-byte aligned (4 KB in every verified case); unaligned hits are other structs.
            if (int(q[k]) & 0xFF) != 0:
                continue
            out.append({"archive": arch, "cpu": v["off"], "gpu": g["off"], "gpu_size": g["size"], "gpu_chain": chain,
                        "data_off": int(q[k]) & 0x0FFFFFFF, "w": w, "h": h, "depth": depth, "b6": d[6], "fmt": fmt,
                        "fmt_name": DXGI.get(fmt, f"dxgi{fmt}"), "flags": int(q[k + 5]), "packed": int(q[k - 2]),
                        "dtype": int(q[k - 1]), "mips": (int(q[k + 5]) >> 16) & 0xFF, "q_index": k})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carve")
    ap.add_argument("--archives")
    ap.add_argument("--out")
    a = ap.parse_args()
    if not os.path.isdir(a.carve):
        ap.error(f"{a.carve} is not a folder")
    archs = a.archives.split(",") if a.archives else sorted(
        d for d in os.listdir(a.carve) if os.path.isfile(os.path.join(a.carve, d, "index.json")))
    missing = [arch for arch in archs if not os.path.isfile(os.path.join(a.carve, arch, "index.json"))]
    if missing:
        ap.error(f"no index.json for {', '.join(missing)} in {a.carve}")
    if not archs:
        ap.error(f"no carved archive (a folder with index.json) in {a.carve}")
    allt = []
    for arch in archs:
        t = scan_archive(a.carve, arch)
        print(f"{arch}: {len(t)} texture headers", flush=True)
        allt += t
    path = a.out or os.path.join(a.carve, "textures_index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(allt, f)
    print(f"{len(allt)} textures -> {path}")
    print("formats:", Counter(t["fmt_name"] for t in allt).most_common(12))
    print("flags (low 16 bits):", Counter(hex(t["flags"] & 0xFFFF) for t in allt).most_common(10))
    print("byte6:", Counter(t["b6"] for t in allt).most_common(8))


if __name__ == "__main__":
    sys.exit(main())
````

## tools/ttpf_mips.py

SHA-256 `23f888ace3a28ce11a101b395c8645b9dc2be99ff702c6ead6f4eccee349580f`

````python
"""Measure and decode TTPF (RDS5) textures: 2D compact mip chains, 2D arrays,
streaming cubemaps, and 3D volumes.

The compact profile in `TtpfReader` is the AMD Gfx10 mip-tail layout: mips smaller
than half a tile share one tile at offset 0, and the rest are standalone, smallest
first. `TtpfReader` only trusts a hand-validated tuple table and stops at the
descriptor's `nonTail` field, which is not the layout boundary. Multi-slice
descriptors use the same 16-byte ETPF record with a 7-bit DXGI format
(`(b >> 3) & 0x7F`) and an 11-bit depth (`((b >> 10) & 0x7FF) + 1`):
  - 2D arrays (`dimension = 1, depth > 1, mode = 1`): mip-major SW_64KB_D.
  - Cubemaps (`dimension = 2, depth = 6, mode = 18 + 2 * non_tail`): `non_tail + 1`
    back-to-back streaming snapshots; the final chunk holds the full-res 6-face
    slice-major SW_4KB_S cubemap.
  - 3D volumes (`dimension = 3, depth > 1, mode = 2, mips = 1`): single-mip 3D
    SW_4KB_S tiling.

The layout rules live in `tex_headers.py`; this tool supplies the RDS5 reader,
decoders and commands. It computes the layout from the descriptor, validates it
against the native allocation span, then decodes zlib/raw mips and supported
BCPack codecs (BC1, BC3, BC4, BC5, BC6H and BC7 via `bcpack.py`, strict
confirmed-history mode by default; pass `--allow-provisional` to opt into
unconfirmed built-in history entries, and `--history <path>` to supply locally
generated BC6H/BC7 initial history tables).

Read-only: no texture bytes are printed or committed. `scan` emits aggregate
counters only (both the zlib/raw baseline and the BCPack-enabled projection).
`layout` prints descriptor fields and offsets. `check` prints the BC
block-average error against a 2x2 downsample of the parent mip (across all
slices/faces for arrays and cubemaps; BC1, BC3, BC4_UNORM and BC5_UNORM) or 3D
Z-continuity vs 2D control for float16 volumes. `export` writes a DX10 DDS when
every source mip uses a supported codec.

    python -I tools/ttpf_mips.py scan <game root or pool paths...> [--json out] [--tuples]
    python -I tools/ttpf_mips.py layout <pool.ttpf> <index>
    python -I tools/ttpf_mips.py check <pool.ttpf> <index> [--allow-provisional] [--history path]
    python -I tools/ttpf_mips.py export <pool.ttpf> <index> <out.dds> [--mips N] [--force] [--allow-provisional] [--history path]

Standard library only. The tile patterns and tail formula are the public AMD
Gfx10 4 KiB/64 KiB layouts recorded in docs/textures.md and docs/textures_arrays.md.
"""
import argparse
import glob
import json
import math
import mmap
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bcpack  # noqa: E402
from tex_headers import (  # noqa: E402
    array_surface_layout, compact_surface_layout, cubemap_surface_layout,
    decode_etpf_chunk_pages, etpf_streaming_padding, gfx10_tile_bytes,
    gfx10_tile_mode, parse_etpf_texture_record, volume_surface_layout,
)

MAX_OUTPUT = 256 * 1024 * 1024
MAX_TEXTURES = 250_000
ETPF_VERSION = 634

# DXGI format -> element bytes, as RageTextureDecoder.ElementBytes. DXGI 11
# (R16G16B16A16_UNORM) is 8 bytes but is left out here as well: its uncompressed
# tiling has not been validated, so `scan` reports it as a format gap.
ELEMENT_BYTES = {
    2: 16, 3: 16, 4: 16, 6: 12, 7: 12, 8: 12, 10: 8, 12: 8, 13: 8, 14: 8,
    16: 8, 17: 8, 18: 8, 24: 4, 25: 4, 26: 4, 28: 4, 29: 4, 30: 4, 31: 4, 32: 4,
    34: 4, 35: 4, 36: 4, 37: 4, 38: 4, 41: 4, 42: 4, 43: 4, 49: 2, 50: 2, 51: 2,
    52: 2, 54: 2, 56: 2, 57: 2, 58: 2, 59: 2, 61: 1, 62: 1, 63: 1, 64: 1, 65: 1,
    71: 8, 72: 8, 74: 16, 75: 16, 77: 16, 78: 16, 80: 8, 81: 8, 83: 16, 84: 16,
    87: 4, 88: 4, 91: 4, 93: 4, 95: 16, 96: 16, 98: 16, 99: 16,
}
BC_FORMATS = frozenset(range(70, 85)) | frozenset(range(94, 100))

# AMD Gfx10 intra-tile bit order (bit index -> source bit), from TtpfReader.
PATTERNS_4K = {
    0: (1, 2, 3, 4, -1, -2, -3, -4, -5, 5, -6, 6),
    1: (0, 1, 2, 3, -1, -2, -3, 4, -4, 5, -5, 6),
    2: (0, 0, 1, 2, -1, -2, -3, 3, -4, 4, -5, 5),
    3: (0, 0, 0, 1, -1, -2, 2, 3, -3, 4, -4, 5),
    4: (0, 0, 0, 0, -1, -2, 1, 2, -3, 3, -4, 4),
}
PATTERNS_64K = {
    0: (1, 2, 3, -2, -1, -3, 4, -4, -5, 5, -6, 6, -7, 7, -8, 8),
    1: (0, 1, 2, 3, -1, -2, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8),
    2: (0, 0, 1, 2, -1, -2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7),
    3: (0, 0, 0, 1, -1, 2, 3, -2, -3, 4, -4, 5, -5, 6, -6, 7),
    4: (0, 0, 0, 0, 1, -1, 2, -2, -3, 3, -4, 4, -5, 5, -6, 6),
}
# AMD Gfx10 3D SW_4KB_S intra-tile bit order (addrlib GFX10_SW_4K_S 3D):
# >0 and <100 = X bit (s-1), <0 = Y bit (-s-1), >=101 = Z bit (s-101).
VOLUME_PATTERNS_4K = {
    0: (1, 2, 101, -1, 102, -2, 3, 103, -3, 4, 104, -4),
    1: (0, 1, 2, 101, -1, 102, 3, -2, 103, 4, -3, 104),
    2: (0, 0, 1, 2, 101, -1, 102, -2, 3, 103, -3, 104),
    3: (0, 0, 0, 1, 101, -1, 2, 102, -2, 3, 103, -3),
    4: (0, 0, 0, 0, 1, -1, 101, 2, -2, 102, 3, 103),
}
VOLUME_FLOAT_FORMATS = {10: 4, 54: 1}  # DXGI format -> float16 channels per voxel

# The profile tuples `TtpfReader.ValidatedCompactProfile` accepts. Reproduced only
# so `scan` can show the reader's published skip/partial split next to the layout
# result; decoding does not depend on this table.
VALIDATED_COMPACT = {
    (4, 1024, 1024, 9, 3, 8, 0x503, 0x00B00106),
    (6, 512, 512, 8, 3, 8, 0x041, 0x00B800D4),
    (4, 256, 256, 7, 1, 8, 0x103, 0),
    (4, 512, 512, 8, 3, 16, 0x482, 0x015000F5),
    (4, 1024, 512, 8, 3, 8, 0x482, 0x015000F5),
    (4, 512, 1024, 8, 3, 8, 0x483, 0x013000F5),
    (4, 128, 256, 6, 1, 8, 0x083, 0),
    (4, 256, 512, 7, 1, 8, 0x167, 0),
    (4, 512, 256, 7, 1, 8, 0x166, 0),
    (4, 256, 256, 7, 1, 16, 0x166, 0),
    (4, 1024, 512, 8, 3, 16, 0x504, 0x900106),
    (4, 1024, 256, 7, 3, 16, 0x484, 0x11000F5),
    (6, 1024, 256, 7, 3, 8, 0x42, 0x9800D4),
    (6, 64, 1024, 5, 3, 8, 0x83, 0x3800B4),
    (4, 512, 1024, 8, 3, 16, 0x503, 0xB00106),
    (4, 512, 128, 6, 1, 16, 0x168, 0),
    (6, 256, 1024, 7, 3, 8, 0x83, 0x3800D4),
    (4, 1024, 128, 6, 1, 8, 0x168, 0),
    (4, 2048, 256, 7, 3, 16, 0x508, 0x100106),
    (4, 2048, 512, 8, 3, 8, 0x504, 0x900106),
    (6, 512, 256, 7, 3, 16, 0x42, 0x9800D4),
    (6, 1024, 128, 6, 3, 16, 0x84, 0x1800D4),
    (4, 512, 128, 6, 1, 8, 0x104, 0),
    (4, 256, 1024, 7, 3, 16, 0x483, 0x13000F5),
    (6, 1024, 64, 5, 3, 16, 0x83, 0x3800B4),
    (6, 256, 512, 7, 3, 16, 0x41, 0xB800D4),
    (4, 128, 128, 6, 1, 16, 0x82, 0),
    (4, 512, 64, 5, 1, 16, 0x108, 0),
    (4, 256, 128, 6, 1, 16, 0x104, 0),
    (6, 128, 1024, 6, 3, 16, 0x83, 0x3800D4),
    (4, 512, 64, 5, 1, 8, 0x84, 0),
    (4, 128, 512, 6, 1, 16, 0x167, 0),
    (4, 256, 128, 6, 1, 8, 0x82, 0),
    (4, 1024, 64, 5, 1, 8, 0x108, 0),
    (6, 1024, 32, 4, 3, 16, 0x82, 0x5800B4),
    (4, 128, 512, 6, 1, 8, 0x107, 0),
    (4, 512, 2048, 8, 3, 8, 0x507, 0x300106),
    (4, 256, 2048, 7, 3, 8, 0x507, 0x3000F5),
    (4, 512, 32, 4, 1, 16, 0x107, 0),
    (6, 128, 1024, 6, 3, 8, 0x83, 0x3800B4),
    (6, 64, 1024, 5, 3, 16, 0x83, 0x3800B4),
    (4, 256, 256, 5, 1, 16, 0x166, 0),
    (4, 128, 256, 6, 1, 16, 0x103, 0),
    (4, 256, 64, 5, 1, 16, 0x84, 0),
    (4, 16, 256, 3, 1, 16, 0x83, 0),
    (4, 256, 32, 4, 1, 16, 0x84, 0),
    (4, 64, 512, 5, 1, 16, 0x107, 0),
    (4, 2048, 256, 7, 3, 8, 0x484, 0x11000F5),
    (4, 64, 512, 5, 1, 8, 0x107, 0),
    (4, 64, 256, 5, 1, 8, 0x83, 0),
    (6, 256, 512, 9, 3, 16, 0x41, 0xB800D4),
    (6, 32, 1024, 4, 3, 16, 0x82, 0x5800B4),
    (4, 512, 512, 3, 3, 8, 0x502, 0xD00006),
    (36, 1024, 1024, 9, 3, 8, 0x503, 0xB00106),
    (36, 256, 256, 7, 1, 8, 0x103, 0),
}
VALIDATED_AUX = dict(mips=3, non_tail=3, meta=0x1A8, extra=0x01080008, width=1024,
                     height_a=512, fmt_a=61, height_b=1024, bytes_b=8)


class LayoutError(ValueError):
    pass


class BcpackRequired(NotImplementedError):
    pass


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


def align(v, n):
    return (v + n - 1) // n * n


def tile_mode(mode):
    """Descriptor mode is a flag bit plus a 4-bit Gfx10 tile mode at bit 1."""
    return gfx10_tile_mode(mode)


def tile_bytes(mode):
    # Tile mode 0 is SW_64KB_D; 1-3 are SW_4KB_S; 9-12 appear only on arrays.
    return gfx10_tile_bytes(mode)


def element_bytes(fmt):
    if fmt not in ELEMENT_BYTES:
        raise LayoutError(f"no element-size mapping for DXGI format {fmt}")
    return ELEMENT_BYTES[fmt]


def surface_layout(width, height, fmt, mips, tile=4096):
    """AMD Gfx10 surface layout: standalone mips smallest-first, then one tail tile."""
    try:
        return compact_surface_layout(width, height, mips, element_bytes(fmt),
                                      4 if fmt in BC_FORMATS else 1, tile)
    except ValueError as exc:
        raise LayoutError(str(exc)) from exc


def detile(layout, mip, tiled):
    """Copy the mip's elements out of the tiled allocation into block-linear order."""
    pat = (PATTERNS_4K if layout["tile"] == 4096 else PATTERNS_64K)[
        {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[layout["element_bytes"]]]
    bw, bh = layout["block_w"], layout["block_h"]
    eb = layout["element_bytes"]
    out = bytearray(mip["blocks_w"] * mip["blocks_h"] * eb)
    for y in range(mip["blocks_h"]):
        for x in range(mip["blocks_w"]):
            off = ((y // bh) * (mip["padded_w"] // bw) + x // bw) * layout["tile"]
            for bit, s in enumerate(pat):
                if s > 0:
                    off |= (((x + mip["tile_x"]) >> (s - 1)) & 1) << bit
                elif s < 0:
                    off |= (((y + mip["tile_y"]) >> (-s - 1)) & 1) << bit
            at = (y * mip["blocks_w"] + x) * eb
            out[at:at + eb] = tiled[off:off + eb]
    return bytes(out)


def detile_volume_slice(layout, tiled, z):
    """Copy one Z slice out of a 3D SW_4KB_S tiled volume into row-major linear order."""
    eb = layout["element_bytes"]
    pat = VOLUME_PATTERNS_4K[{1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[eb]]
    bw, bh, bd = layout["block_w"], layout["block_h"], layout["block_d"]
    mip = layout["mips"][0]
    w, h = mip["blocks_w"], mip["blocks_h"]
    tiles_x = mip["padded_w"] // bw
    z_base = (z // bd) * layout["z_tile_stride"]
    z_in_tile = 0
    for bit, s in enumerate(pat):
        if s >= 101:
            z_in_tile |= ((z >> (s - 101)) & 1) << bit
    out = bytearray(w * h * eb)
    for y in range(h):
        y_tile = (y // bh) * tiles_x
        y_in_tile = z_in_tile
        for bit, s in enumerate(pat):
            if s < 0:
                y_in_tile |= ((y >> (-s - 1)) & 1) << bit
        row_at = y * w * eb
        for x in range(w):
            off = z_base + (y_tile + x // bw) * layout["tile"] + y_in_tile
            for bit, s in enumerate(pat):
                if 0 < s < 100:
                    off |= ((x >> (s - 1)) & 1) << bit
            at = row_at + x * eb
            out[at:at + eb] = tiled[off:off + eb]
    return bytes(out)


def detile_volume(layout, tiled):
    """Detile all Z slices of a 3D SW_4KB_S volume into Z-major linear order."""
    return b"".join(detile_volume_slice(layout, tiled, z) for z in range(layout["depth"]))


# --- BC decoding (color only; enough for the downsample check) -------------

def _rgb565(c):
    return ((c >> 11) & 31) * 255.0 / 31, ((c >> 5) & 63) * 255.0 / 63, (c & 31) * 255.0 / 31


def decode_bc1_block(data, at, four_color=False):
    c0, c1, idx = struct.unpack_from("<HHI", data, at)
    p0, p1 = _rgb565(c0), _rgb565(c1)
    if four_color or c0 > c1:
        pal = [p0, p1, tuple((2 * a + b) / 3 for a, b in zip(p0, p1)),
               tuple((a + 2 * b) / 3 for a, b in zip(p0, p1))]
    else:
        pal = [p0, p1, tuple((a + b) / 2 for a, b in zip(p0, p1)), (0.0, 0.0, 0.0)]
    return [pal[(idx >> (2 * (y * 4 + x))) & 3] for y in range(4) for x in range(4)]


def decode_bc4_block(data, at):
    e0, e1 = data[at], data[at + 1]
    bits = int.from_bytes(data[at + 2:at + 8], "little")
    if e0 > e1:
        pal = [e0, e1] + [((7 - i) * e0 + i * e1) // 7 for i in range(1, 7)]
    else:
        pal = [e0, e1] + [((5 - i) * e0 + i * e1) // 5 for i in range(1, 5)] + [0, 255]
    vals = [pal[(bits >> (3 * (y * 4 + x))) & 7] for y in range(4) for x in range(4)]
    return [(float(v),) * 3 for v in vals]


def decode_pixels(fmt, data, blocks_w, blocks_h):
    """Return one (r, g, b) per pixel, or None for a format this tool cannot decode."""
    px = []
    for by in range(blocks_h):
        rows = [[None] * (blocks_w * 4) for _ in range(4)]
        for bx in range(blocks_w):
            at = (by * blocks_w + bx) * 16
            if fmt in (71, 72):
                blk = decode_bc1_block(data, (by * blocks_w + bx) * 8)
            elif fmt in (77, 78):
                # BC3 colour uses four entries regardless of endpoint order.
                blk = decode_bc1_block(data, at + 8, four_color=True)
            elif fmt in (80,):
                blk = decode_bc4_block(data, (by * blocks_w + bx) * 8)
            elif fmt in (83,):
                a = decode_bc4_block(data, at)
                b = decode_bc4_block(data, at + 8)
                blk = [(p[0], q[0], 0.0) for p, q in zip(a, b)]
            else:
                return None
            for y in range(4):
                for x in range(4):
                    rows[y][bx * 4 + x] = blk[y * 4 + x]
        px.extend(rows)
    return [p for row in px for p in row]


def block_means(pixels, blocks_w, blocks_h, pixels_w=None, pixels_h=None):
    pw = blocks_w * 4 if pixels_w is None else pixels_w
    ph = blocks_h * 4 if pixels_h is None else pixels_h
    out = []
    for by in range(blocks_h):
        for bx in range(blocks_w):
            acc = [0.0, 0.0, 0.0]
            n = 0
            for y in range(4):
                if by * 4 + y >= ph:
                    continue
                for x in range(4):
                    if bx * 4 + x >= pw:
                        continue
                    q = pixels[(by * 4 + y) * (blocks_w * 4) + bx * 4 + x]
                    for k in range(3):
                        acc[k] += q[k]
                    n += 1
            out.append((acc[0] / n, acc[1] / n, acc[2] / n) if n else (0.0, 0.0, 0.0))
    return out


def downsample2(blocks, blocks_w, blocks_h):
    ow, oh = max(1, blocks_w // 2), max(1, blocks_h // 2)
    out = []
    for y in range(oh):
        for x in range(ow):
            acc = [0.0, 0.0, 0.0]
            n = 0
            for dy in range(2):
                for dx in range(2):
                    bx = min(blocks_w - 1, 2 * x + dx)
                    by = min(blocks_h - 1, 2 * y + dy)
                    q = blocks[by * blocks_w + bx]
                    for k in range(3):
                        acc[k] += q[k]
                    n += 1
            out.append(tuple(a / n for a in acc))
    return out


def mean_abs_error(a, b):
    if not a:
        return None
    return sum(abs(x - y) for pa, pb in zip(a, b) for x, y in zip(pa, pb)) / (3 * len(a))


# --- RDS5 / ETPF container ------------------------------------------------

class Pool:
    """Read-only RDS5 texture pool, mirroring TtpfReader's catalog checks."""

    def __init__(self, path):
        # A pool that fails a check used to keep its file open and mapped (locked on Windows).
        self._fh = self.data = None
        try:
            self._open(path)
        except Exception:
            self.close()
            raise

    def _open(self, path):
        self.path = path
        self._fh = open(path, "rb")
        try:
            self.data = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        except Exception:
            self._fh.close()
            raise
        d = self.data
        if len(d) < 256 or d[:4] != b"RDS5":
            raise ValueError("not an RDS5 container or truncated header")
        count = u32(d, 4)
        size_word = u64(d, 8)
        self.virtual_size = size_word & 0x00FFFFFFFFFFFFFF
        if (count < 3 or count > 1_000_002 or (size_word >> 56) != 22 or
                self.virtual_size < 4096 or u32(d, 16) not in
                ((count + 31) // 32, (count + 31) // 32 + 1)):
            raise ValueError("unsupported RDS5 index layout")
        self.chunk_count = count - 2
        table_end = 24 + (count - 1) * 8
        self.etpf = align(table_end, 256)
        if table_end > len(d) - 16:
            raise ValueError("RDS5 index exceeds its source")
        table = d[24:table_end]
        if ((u64(table, len(table) - 8) & 0x3FFFFFF) * 256 != len(d) or
                ((u64(table, len(table) - 8) >> 30) & 0x3FFFFF) * 4096 != self.virtual_size):
            raise ValueError("RDS5 sentinel does not match its lengths")
        self.chunks = []
        for i in range(self.chunk_count):
            v, nxt = u64(table, i * 8), u64(table, (i + 1) * 8)
            start, end = (v & 0x3FFFFFF) * 256, (nxt & 0x3FFFFFF) * 256
            virt, vend = ((v >> 30) & 0x3FFFFF) * 4096, ((nxt >> 30) & 0x3FFFFF) * 4096
            pad = v >> 52
            codec = (v >> 26) & 15
            packed, size = end - start - pad, vend - virt
            if (start < self.etpf + 16 or end > len(d) or packed < 1 or packed > MAX_OUTPUT or
                    size < 1 or size > MAX_OUTPUT or vend > self.virtual_size or
                    (codec == 0 and packed != size)):
                raise ValueError(f"RDS5 chunk {i} range is invalid")
            self.chunks.append((virt, size, start, packed, codec, pad))
        eh = d[self.etpf:self.etpf + 16]
        if eh[:4] != b"ETPF" or u32(eh, 4) != ETPF_VERSION:
            raise ValueError("unsupported embedded ETPF version")
        self.textures = u32(eh, 8)
        area = u32(eh, 12)
        metadata = 16 + area + self.textures * 32
        padded = align(metadata, 4096)
        alignment = u32(d, 20)
        source_padding = (alignment >> 28) * 256
        if (self.textures < 1 or self.textures > MAX_TEXTURES or area < self.textures * 16 or
                (alignment & 0x0FFFFFFF) != 0 or padded != self.chunks[0][0] or
                self.etpf + padded + source_padding != self.chunks[0][2]):
            raise ValueError("ETPF tables do not match the data boundary")
        self.area = area
        self.records = d[self.etpf + 16:self.etpf + 16 + area]
        self.ids = d[self.etpf + 16 + area:self.etpf + 16 + area + self.textures * 32]
        self._starts = [c[0] for c in self.chunks]

    def close(self):
        if self.data is not None:
            self.data.close()
        if self._fh is not None:
            self._fh.close()

    def descriptor(self, index):
        if not 0 <= index < self.textures:
            raise IndexError(index)
        d = parse_etpf_texture_record(self.records[index * 16:index * 16 + 16])
        d["index"] = index
        d["asset_key_at"] = (
            u64(self.records, self.textures * 16 + index * 8)
            if (self.textures * 16 + index * 8 + 8 <= len(self.records))
            else None)
        return d

    def chunks_for(self, start, size):
        import bisect
        end = start + size
        i = max(0, bisect.bisect_right(self._starts, start) - 1)
        out = []
        covered = start
        while i < len(self.chunks) and self.chunks[i][0] < end:
            virt, csize, src, packed, codec, pad = self.chunks[i]
            if virt > covered:
                raise ValueError("texture crosses an unmapped virtual range")
            out.append(self.chunks[i])
            covered = min(end, virt + csize)
            i += 1
        if covered != end:
            raise ValueError("texture range is not completely mapped")
        return out

    def codecs(self, start, size):
        return {c[4] for c in self.chunks_for(start, size)}

    def readable(self, start, size, *, allow_bcpack=False):
        allowed = ({0, 8} | bcpack.SUPPORTED_REBUILD_CODECS) if allow_bcpack else {0, 8}
        return self.codecs(start, size) <= allowed

    def read_range(self, start, size, cache=None, *, bcpack_mode="strict", bcpack_history=None):
        if bcpack_mode not in ("strict", "provisional", "off"):
            raise ValueError(f"invalid bcpack_mode: {bcpack_mode!r}")
        cache = {} if cache is None else cache
        out = bytearray(size)
        hist_key = None if bcpack_history is None else (
            id(bcpack_history) if isinstance(bcpack_history, dict) else os.fspath(bcpack_history)
        )
        for virt, csize, src, packed, codec, pad in self.chunks_for(start, size):
            key = (src, packed, codec, bcpack_mode if codec not in (0, 8) else "raw",
                   hist_key if codec in (6, 7) else None)
            if key not in cache:
                raw = self.data[src:src + packed]
                if codec == 0:
                    cache[key] = bytes(raw)
                elif codec == 8:
                    cache[key] = zlib.decompress(raw)
                elif bcpack_mode != "off" and codec in bcpack.SUPPORTED_REBUILD_CODECS:
                    cache[key] = bcpack.decode(
                        raw, codec, csize,
                        allow_provisional=(bcpack_mode == "provisional"),
                        history=bcpack_history,
                    )
                else:
                    raise BcpackRequired(
                        f"range touches a BCPack chunk (codec {codec})"
                    )
                if len(cache[key]) != csize:
                    raise ValueError("decoded chunk length disagrees with its range")
            lo, hi = max(start, virt), min(start + size, virt + csize)
            out[lo - start:hi - start] = cache[key][lo - virt:hi - virt]
        return bytes(out)

    def span(self, index, base):
        for j in range(index + 1, self.textures):
            cand = (u32(self.records, j * 16 + 8) & 0x1FFFFF) * 4096
            if cand < base:
                return None
            if cand > base:
                return cand - base
        return self.virtual_size - base


def compact_row(desc):
    """The reader's compact-profile gate (mode families 4/6/36 and aux mode 2)."""
    return desc["mode"] in (4, 6, 36) or (desc["mode"] == 2 and (desc["meta"] or desc["extra"]))


def validated_compact(desc, eb):
    return (desc["mode"], desc["width"], desc["height"], desc["mips"], desc["non_tail"],
            eb, desc["meta"], desc["extra"]) in VALIDATED_COMPACT


def validated_aux(desc):
    a = VALIDATED_AUX
    return (desc["mips"] == a["mips"] and desc["non_tail"] == a["non_tail"] and
            desc["meta"] == a["meta"] and desc["extra"] == a["extra"] and
            desc["width"] == a["width"] and
            ((desc["height"] == a["height_a"] and desc["format"] == a["fmt_a"]) or
             (desc["height"] == a["height_b"] and desc["format"] in BC_FORMATS and
              ELEMENT_BYTES.get(desc["format"]) == a["bytes_b"])))


def validate_chunk_metadata(pool, desc, span):
    """Verify ``(meta, extra)`` streaming chunk sizes and alignment padding.

    Returns ``(ok, pages)`` where ``pages`` is the decoded tuple of 4 KiB chunk
    page counts (empty when ``meta == 0 and extra == 0``).
    """
    meta, extra = desc["meta"], desc["extra"]
    if meta == 0 and extra == 0:
        return True, ()
    pages = decode_etpf_chunk_pages(meta, extra)
    if not pages:
        return False, None
    try:
        chunks = pool.chunks_for(desc["base"], span)
    except ValueError:
        return False, None
    if len(chunks) != len(pages):
        return False, None
    if chunks[0][0] != desc["base"] or sum(c[1] for c in chunks) != span:
        return False, None
    for chunk, expected_pages in zip(chunks, pages):
        if chunk[1] != expected_pages * 4096:
            return False, None
    align_group, pad_pages = etpf_streaming_padding(extra)
    if desc["dimension"] == 2 or desc["non_tail"] == 1:
        if align_group != 0 or pad_pages != 0:
            return False, None
    elif desc["dimension"] == 1 and desc["non_tail"] == 3:
        if align_group == 1:
            if pages[0] + pad_pages != 16:
                return False, None
        elif align_group == 2:
            if len(pages) < 2 or pages[0] + pages[1] + pad_pages != 16:
                return False, None
        elif align_group == 3:
            if len(pages) < 2 or pages[0] + pages[1] + pad_pages != 8:
                return False, None
        else:
            return False, None
    else:
        if align_group != 0 or pad_pages != 0:
            return False, None
    return True, pages


def _mip_range_codecs(pool, base, offset, region, slices=1, slice_stride=0):
    codecs = set()
    for s in range(slices):
        codecs |= pool.codecs(base + offset + s * slice_stride, region)
    return codecs


def _decode_volume_voxels(fmt, data, width, height, depth):
    """Decode float16 volume bytes into a flat list of per-voxel float tuples."""
    channels = VOLUME_FLOAT_FORMATS.get(fmt)
    if channels is None:
        return None
    n = width * height * depth * channels
    vals = struct.unpack_from(f"<{n}e", data, 0)
    if channels == 1:
        return [(v,) for v in vals]
    return [vals[i:i + channels] for i in range(0, n, channels)]


def _volume_z_diff(voxels, width, height, depth):
    """Mean absolute difference between adjacent Z slices (finite voxels only)."""
    plane = width * height
    total = 0.0
    count = 0
    for z in range(depth - 1):
        a0 = z * plane
        b0 = (z + 1) * plane
        for p in range(plane):
            va = voxels[a0 + p]
            vb = voxels[b0 + p]
            for ca, cb in zip(va, vb):
                if math.isfinite(ca) and math.isfinite(cb):
                    total += abs(ca - cb)
                    count += 1
    return (total / count) if count else None


def analyze(pool, index, *, allow_bcpack=True):
    """Descriptor + layout + per-mip codec availability for one texture."""
    d = pool.descriptor(index)
    out = dict(descriptor=d, tile_mode=tile_mode(d["mode"]), tile=tile_bytes(d["mode"]))
    if d["base"] == 0 or (d["base"] >> 12) == 0x1FFFFF:
        out["blocked"] = "no mapped allocation"
        return out
    span = pool.span(index, d["base"])
    out["allocation_span"] = span
    allowed = ({0, 8} | bcpack.SUPPORTED_REBUILD_CODECS) if allow_bcpack else {0, 8}

    if d["dimension"] == 1 and d["depth"] == 1:
        out["shape"] = "2d"
        try:
            layout = surface_layout(d["width"], d["height"], d["format"], d["mips"],
                                    out["tile"])
        except LayoutError as e:
            out["blocked"] = str(e)
            return out
        out["layout"] = layout
        out["span_matches"] = span == layout["size"]
        if not out["span_matches"]:
            out["blocked"] = "layout does not match the allocation span"
            return out
        avail = []
        mip_codecs = []
        for mip in layout["mips"]:
            try:
                cs = pool.codecs(d["base"] + mip["offset"], mip["region"])
                mip_codecs.append(sorted(cs))
                avail.append(cs <= allowed)
            except ValueError:
                avail = []
                mip_codecs = []
                break
        out["available"] = avail
        out["mip_codecs"] = mip_codecs
        if avail:
            limit = d["non_tail"] if compact_row(d) else d["mips"]
            limit = max(0, min(limit, len(avail)))
            base_mip = next((i for i in range(limit) if avail[i]), None)
            exported = 0
            if base_mip is not None:
                while base_mip + exported < limit and avail[base_mip + exported]:
                    exported += 1
            out["reader_limit"] = limit
            out["reader_base_mip"] = base_mip
            out["reader_exported"] = exported
            out["full_chain"] = bool(avail) and all(avail)
            out["recoverable_mips"] = sum(1 for a in avail[exported:] if a) if base_mip == 0 else 0
        return out

    if d["dimension"] == 1 and d["depth"] > 1:
        out["shape"] = "2d_array"
        if d["mode"] != 1:
            out["blocked"] = f"unsupported 2D array mode {d['mode']}"
            return out
        try:
            eb = element_bytes(d["format"])
            blk = 4 if d["format"] in BC_FORMATS else 1
            layout = array_surface_layout(d["width"], d["height"], d["depth"], d["mips"],
                                          eb, blk, out["tile"])
        except (LayoutError, ValueError) as e:
            out["blocked"] = str(e)
            return out
        out["layout"] = layout
        out["span_matches"] = span == layout["size"]
        if not out["span_matches"]:
            out["blocked"] = "array layout does not match the allocation span"
            return out
        avail = []
        mip_codecs = []
        for mip in layout["mips"]:
            try:
                cs = _mip_range_codecs(pool, d["base"], mip["offset"], mip["region"],
                                       d["depth"], mip["slice_stride"])
                mip_codecs.append(sorted(cs))
                avail.append(cs <= allowed)
            except ValueError:
                avail = []
                mip_codecs = []
                break
        out["available"] = avail
        out["mip_codecs"] = mip_codecs
        if avail:
            out["reader_limit"] = 0
            out["reader_base_mip"] = None
            out["reader_exported"] = 0
            out["full_chain"] = all(avail)
        return out

    if d["dimension"] == 2:
        out["shape"] = "cubemap"
        if d["depth"] != 6:
            out["blocked"] = f"unsupported cubemap depth {d['depth']}"
            return out
        if d["non_tail"] > 3 or d["mode"] != 18 + 2 * d["non_tail"]:
            out["blocked"] = f"unsupported cubemap mode {d['mode']} (non_tail={d['non_tail']})"
            return out
        ok, pages = validate_chunk_metadata(pool, d, span)
        if not ok:
            out["blocked"] = "cubemap streaming chunk metadata mismatch"
            return out
        if d["non_tail"] > 0 and len(pages) != d["non_tail"] + 1:
            out["blocked"] = "cubemap streaming chunk metadata mismatch"
            return out
        if d["non_tail"] == 0 and len(pages) not in (0, 1):
            out["blocked"] = "cubemap chunk metadata mismatch"
            return out
        try:
            eb = element_bytes(d["format"])
            blk = 4 if d["format"] in BC_FORMATS else 1
            layout = cubemap_surface_layout(d["width"], d["height"], d["mips"], eb, blk,
                                            d["non_tail"], pages if pages else None)
        except (LayoutError, ValueError) as e:
            out["blocked"] = str(e)
            return out
        out["layout"] = layout
        out["span_matches"] = span == layout["size"]
        if not out["span_matches"]:
            out["blocked"] = "cubemap layout does not match the allocation span"
            return out
        avail = []
        mip_codecs = []
        face_base = d["base"] + layout["data_offset"]
        for mip in layout["mips"]:
            try:
                cs = _mip_range_codecs(pool, face_base, mip["offset"], mip["region"],
                                       6, layout["face_size"])
                mip_codecs.append(sorted(cs))
                avail.append(cs <= allowed)
            except ValueError:
                avail = []
                mip_codecs = []
                break
        out["available"] = avail
        out["mip_codecs"] = mip_codecs
        if avail:
            out["reader_limit"] = 0
            out["reader_base_mip"] = None
            out["reader_exported"] = 0
            out["full_chain"] = all(avail)
        return out

    if d["dimension"] == 3:
        out["shape"] = "volume"
        if d["mode"] != 2 or d["mips"] != 1 or d["format"] in BC_FORMATS:
            out["blocked"] = (
                f"unsupported 3D volume mode={d['mode']} mips={d['mips']} format={d['format']}")
            return out
        try:
            eb = element_bytes(d["format"])
            layout = volume_surface_layout(d["width"], d["height"], d["depth"], d["mips"], eb)
        except (LayoutError, ValueError) as e:
            out["blocked"] = str(e)
            return out
        out["layout"] = layout
        out["span_matches"] = span == layout["size"]
        if not out["span_matches"]:
            out["blocked"] = "volume layout does not match the allocation span"
            return out
        try:
            cs = pool.codecs(d["base"], layout["size"])
            avail = [cs <= allowed]
            mip_codecs = [sorted(cs)]
        except ValueError:
            avail = []
            mip_codecs = []
        out["available"] = avail
        out["mip_codecs"] = mip_codecs
        if avail:
            out["reader_limit"] = 0
            out["reader_base_mip"] = None
            out["reader_exported"] = 0
            out["full_chain"] = avail[0]
        return out

    out["shape"] = "unknown"
    out["blocked"] = f"unsupported descriptor dimension {d['dimension']}"
    return out


# --- commands --------------------------------------------------------------

def find_pools(arg):
    if os.path.isfile(arg):
        return [arg]
    pools = sorted(glob.glob(os.path.join(arg, "data", "ttdb", "**", "*.ttpf"), recursive=True))
    pools += sorted(glob.glob(os.path.join(arg, "pack", "*", "data", "ttdb", "**", "*.ttpf"),
                                recursive=True))
    return pools


def scan_pools(paths, as_json=None, include_tuples=False):
    total = dict(pools=0, entries=0, arrays=0, arrays_2d=0, arrays_2d_full=0,
                 arrays_2d_partial=0, arrays_2d_bcpack=0, cubemaps=0, cubemaps_full=0,
                 cubemaps_partial=0, cubemaps_bcpack=0, volumes=0, volumes_full=0,
                 volumes_bcpack=0, multi_slice_layout_mismatch=0,
                 chunk_metadata_ok=0, chunk_metadata_fail=0,
                 unsupported_format=0, format11=0,
                 layout_mismatch=0, reader_full=0, reader_partial=0,
                 reader_skip_bcpack=0, whitelist_gated=0, gated_layout_ok=0,
                 gated_full_chain=0, gated_full_mips=0, gated_full_bytes=0,
                 gated_tail_only=0, gated_partial=0, gated_no_contiguous=0,
                 gated_no_layout=0, gated_unknown_format=0,
                 gated_other_layout_error=0, gated_span_mismatch=0,
                 gated_unreadable_range=0, gated_tuple_distinct=0, gated_by_mode={},
                 compact_partial_rows=0, compact_missing_mips=0,
                 compact_decodable_mips=0, compact_decodable_bytes=0,
                 compact_missing_standalone=0, compact_missing_tail=0,
                 compact_rows_measured=0, compact_non_tail_before_tail=0,
                 compact_standalone_beyond_limit=0,
                 compact_standalone_decodable_beyond_limit=0,
                 compact_full_rows=0, after_bcpack_full=0,
                 after_bcpack_partial=0, tile_modes={})
    gated_tuples = {}
    bcpack_allowed = {0, 8} | bcpack.SUPPORTED_REBUILD_CODECS
    for path in paths:
        try:
            pool = Pool(path)
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path}: {exc}") from None
        try:
            total["pools"] += 1
            for i in range(pool.textures):
                d = pool.descriptor(i)
                total["entries"] += 1
                tm = str(tile_mode(d["mode"]))
                total["tile_modes"][tm] = total["tile_modes"].get(tm, 0) + 1
                span = pool.span(i, d["base"]) if d["base"] else None
                if span is not None:
                    meta_ok, _ = validate_chunk_metadata(pool, d, span)
                    if meta_ok:
                        total["chunk_metadata_ok"] += 1
                    else:
                        total["chunk_metadata_fail"] += 1
                if d["dimension"] != 1 or d["depth"] != 1:
                    total["arrays"] += 1
                    a = analyze(pool, i, allow_bcpack=False)
                    shape = a.get("shape")
                    prefix = {"2d_array": "arrays_2d", "cubemap": "cubemaps",
                              "volume": "volumes"}.get(shape)
                    if prefix:
                        total[prefix] += 1
                    if "available" not in a or not a["available"]:
                        total["multi_slice_layout_mismatch"] += 1
                        continue
                    avail = a["available"]
                    mip_codecs = a.get("mip_codecs") or []
                    avail_bc = [set(cs) <= bcpack_allowed for cs in mip_codecs]
                    if prefix:
                        if all(avail):
                            total[f"{prefix}_full"] += 1
                        elif any(avail):
                            if f"{prefix}_partial" in total:
                                total[f"{prefix}_partial"] += 1
                        else:
                            total[f"{prefix}_bcpack"] += 1
                    if avail_bc and all(avail_bc):
                        total["after_bcpack_full"] += 1
                    elif any(avail_bc):
                        total["after_bcpack_partial"] += 1
                    continue
                # The reader's gate: modes 4/6/36 and aux mode 2 need a validated tuple;
                # every other non-0/2 mode is rejected by the same branch.
                aux = d["mode"] == 2 and (d["meta"] or d["extra"])
                if d["mode"] in (0, 2):
                    gated = d["mode"] == 2 and aux and not validated_aux(d)
                else:
                    eb = ELEMENT_BYTES.get(d["format"])
                    gated = not (d["mode"] in (4, 6, 36) and eb is not None and
                                 validated_compact(d, eb))
                try:
                    layout = surface_layout(d["width"], d["height"], d["format"],
                                            d["mips"], tile_bytes(d["mode"]))
                except LayoutError:
                    total["unsupported_format"] += 1
                    if d["format"] == 11:
                        total["format11"] += 1
                    if gated:
                        total["whitelist_gated"] += 1
                        total["gated_no_layout"] += 1
                        if d["format"] not in ELEMENT_BYTES:
                            total["gated_unknown_format"] += 1
                        else:
                            total["gated_other_layout_error"] += 1
                    continue
                if d["base"] == 0 or span != layout["size"]:
                    total["layout_mismatch"] += 1
                    if gated:
                        total["whitelist_gated"] += 1
                        total["gated_span_mismatch"] += 1
                    continue
                avail = []
                avail_bc = []
                for mip in layout["mips"]:
                    try:
                        cs = pool.codecs(d["base"] + mip["offset"], mip["region"])
                    except ValueError:
                        avail = []
                        avail_bc = []
                        break
                    avail.append(cs <= {0, 8})
                    avail_bc.append(cs <= bcpack_allowed)
                if not avail:
                    total["layout_mismatch"] += 1
                    if gated:
                        total["whitelist_gated"] += 1
                        total["gated_unreadable_range"] += 1
                    continue
                if all(avail_bc):
                    total["after_bcpack_full"] += 1
                else:
                    ft = layout["first_tail"]
                    usable_tail_bc = (ft < d["mips"] and all(avail_bc[ft:]))
                    lim_bc = (d["mips"] if (not compact_row(d) or usable_tail_bc)
                              else min(ft, len(avail_bc)))
                    bm_bc = next((k for k in range(lim_bc) if avail_bc[k]), None)
                    exp_bc = 0
                    if bm_bc is not None:
                        while bm_bc + exp_bc < lim_bc and avail_bc[bm_bc + exp_bc]:
                            exp_bc += 1
                    if exp_bc:
                        total["after_bcpack_partial"] += 1
                if gated:
                    total["whitelist_gated"] += 1
                    total["gated_layout_ok"] += 1
                    key = str(d["mode"])
                    total["gated_by_mode"][key] = total["gated_by_mode"].get(key, 0) + 1
                    tuple_key = (d["mode"], d["width"], d["height"], d["mips"],
                                 d["non_tail"], layout["element_bytes"])
                    gated_tuples[tuple_key] = gated_tuples.get(tuple_key, 0) + 1
                    first_tail = layout["first_tail"]
                    if all(avail):
                        total["gated_full_chain"] += 1
                        total["gated_full_mips"] += d["mips"]
                        total["gated_full_bytes"] += sum(
                            mip["blocks_w"] * mip["blocks_h"] * layout["element_bytes"]
                            for mip in layout["mips"])
                    else:
                        # After the layout fix the export limit is the usable
                        # tail tile, or the computed tail boundary when it is
                        # not. Count what would still export and what would not.
                        usable_tail = (first_tail < d["mips"] and
                                       all(avail[first_tail:]))
                        if usable_tail:
                            total["gated_tail_only"] += 1
                            limit = d["mips"]
                        else:
                            limit = min(first_tail, len(avail))
                        base_mip = next((k for k in range(limit) if avail[k]), None)
                        exported = 0
                        if base_mip is not None:
                            while base_mip + exported < limit and avail[base_mip + exported]:
                                exported += 1
                        if exported:
                            total["gated_partial"] += 1
                        else:
                            total["gated_no_contiguous"] += 1
                    continue
                is_compact = compact_row(d)
                limit = min(d["non_tail"], len(avail)) if is_compact else len(avail)
                base_mip = next((k for k in range(limit) if avail[k]), None)
                exported = 0
                if base_mip is not None:
                    while base_mip + exported < limit and avail[base_mip + exported]:
                        exported += 1
                if exported == 0:
                    total["reader_skip_bcpack"] += 1
                elif exported < d["mips"]:
                    total["reader_partial"] += 1
                    if is_compact and base_mip == 0 and exported == limit:
                        total["compact_partial_rows"] += 1
                        missing = d["mips"] - exported
                        total["compact_missing_mips"] += missing
                        dec = 0
                        for k in range(exported, d["mips"]):
                            if avail[k]:
                                dec += 1
                                if k < layout["first_tail"]:
                                    total["compact_missing_standalone"] += 1
                                else:
                                    total["compact_missing_tail"] += 1
                        total["compact_decodable_mips"] += dec
                        total["compact_decodable_bytes"] += sum(
                            layout["mips"][k]["blocks_w"] * layout["mips"][k]["blocks_h"] *
                            layout["element_bytes"] for k in range(exported, d["mips"])
                            if avail[k])
                        if dec == missing:
                            total["compact_full_rows"] += 1
                else:
                    total["reader_full"] += 1
                if d["mode"] in (4, 6, 36):
                    total["compact_rows_measured"] += 1
                    if d["non_tail"] < layout["first_tail"]:
                        total["compact_non_tail_before_tail"] += 1
                        total["compact_standalone_beyond_limit"] += (
                            layout["first_tail"] - d["non_tail"])
                        total["compact_standalone_decodable_beyond_limit"] += sum(
                            1 for k in range(d["non_tail"], layout["first_tail"]) if avail[k])
        finally:
            pool.close()
    total["gated_accounted"] = (total["gated_layout_ok"] + total["gated_no_layout"] +
                                total["gated_span_mismatch"] + total["gated_unreadable_range"])
    total["gated_tuple_distinct"] = len(gated_tuples)
    # Projected split once the reader uses the computed 2D + multi-slice layouts:
    # existing full exports plus compact partials, gated 2D records, and resolved
    # arrays/cubemaps/volumes that complete; partials lose completed 2D rows and
    # gain newly partial gated 2D + array rows.
    total["after_full"] = (total["reader_full"] + total["compact_full_rows"] +
                           total["gated_full_chain"] + total["arrays_2d_full"] +
                           total["cubemaps_full"] + total["volumes_full"])
    total["after_partial"] = (total["reader_partial"] - total["compact_full_rows"] +
                              total["gated_partial"] + total["arrays_2d_partial"] +
                              total["cubemaps_partial"])
    total["after_skip"] = total["entries"] - total["after_full"] - total["after_partial"]
    total["after_bcpack_skip"] = (total["entries"] - total["after_bcpack_full"] -
                                  total["after_bcpack_partial"])
    total["bcpack_unlocked_full"] = total["after_bcpack_full"] - total["after_full"]
    if include_tuples:
        total["gated_tuples"] = [
            {"tuple": list(key), "count": count}
            for key, count in sorted(gated_tuples.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
    report = dict(total=total)
    if as_json:
        with open(as_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


def describe(pool, index):
    a = analyze(pool, index)
    d = a["descriptor"]
    out = dict(index=index, shape=a.get("shape"), width=d["width"], height=d["height"],
               depth=d["depth"], dimension=d["dimension"], format=d["format"],
               mips=d["mips"], non_tail=d["non_tail"], mode=d["mode"],
               tile_mode=a["tile_mode"], tile=a["tile"], base=d["base"],
               meta=d["meta"], extra=d["extra"])
    if "layout" in a:
        lay = a["layout"]
        out["allocation_size"] = lay["size"]
        out["allocation_span"] = a.get("allocation_span")
        out["span_matches"] = a.get("span_matches")
        out["first_tail_mip"] = lay["first_tail"]
        mip_codecs = a.get("mip_codecs") or []
        if a.get("shape") == "cubemap":
            out["data_offset"] = lay["data_offset"]
            out["face_size"] = lay["face_size"]
            out["snapshots"] = lay["snapshots"]
        elif a.get("shape") == "volume":
            out["block_d"] = lay["block_d"]
            out["padded_d"] = lay["padded_d"]
            out["z_tile_stride"] = lay["z_tile_stride"]
        out["mips_detail"] = [
            dict(index=m["index"], blocks=[m["blocks_w"], m["blocks_h"]], offset=m["offset"],
                 region=m["region"], tail=m["in_tail"], tile_origin=[m["tile_x"], m["tile_y"]],
                 **({"slice_stride": m["slice_stride"]} if "slice_stride" in m else {}),
                 **({"codecs": mip_codecs[m["index"]]} if m["index"] < len(mip_codecs) else {}))
            for m in lay["mips"]]
    if "available" in a:
        out["available"] = a["available"]
        out["reader_limit"] = a["reader_limit"]
        out["reader_exported"] = a["reader_exported"]
        out["full_chain"] = a["full_chain"]
    if a.get("blocked"):
        out["blocked"] = a["blocked"]
    return out


def _check_mip_chain_means(layout, fmt, slice_bytes_fn):
    """Detile every mip of one 2D slice and return (means_per_mip, mip_errors)."""
    means = []
    for mip in layout["mips"]:
        data = detile(layout, mip, slice_bytes_fn(mip))
        px = decode_pixels(fmt, data, mip["blocks_w"], mip["blocks_h"])
        means.append(None if px is None else block_means(
            px, mip["blocks_w"], mip["blocks_h"], mip["pixels_w"], mip["pixels_h"]))
    errs = []
    for k in range(1, len(layout["mips"])):
        if means[k - 1] is None or means[k] is None:
            errs.append(None)
            continue
        pm = layout["mips"][k - 1]
        errs.append(round(mean_abs_error(downsample2(means[k - 1], pm["blocks_w"], pm["blocks_h"]),
                                         means[k]), 2))
    return means, errs


def _read_range_or_block(pool, start, size, cache, bcpack_mode, index, shape=None,
                         bcpack_history=None):
    try:
        return pool.read_range(start, size, cache, bcpack_mode=bcpack_mode,
                               bcpack_history=bcpack_history)
    except BcpackRequired as exc:
        msg = dict(index=index, blocked=str(exc))
    except bcpack.BcpackProvisionalError as exc:
        msg = dict(
            index=index,
            blocked=f"provisional BCPack history required ({exc}); pass --allow-provisional",
        )
    except (OSError, ValueError) as exc:
        msg = dict(index=index, blocked=str(exc))
    if shape is not None:
        msg["shape"] = shape
    print(json.dumps(msg, indent=1))
    return None


def check(pool, index, *, allow_provisional=False, history=None):
    a = analyze(pool, index)
    if "layout" not in a or "available" not in a or a.get("blocked"):
        print(json.dumps(dict(index=index, blocked=a.get("blocked")), indent=1))
        return 2
    layout = a["layout"]
    d = a["descriptor"]
    shape = a.get("shape", "2d")
    cache = {}
    bcpack_mode = "provisional" if allow_provisional else "strict"

    if shape == "volume":
        if d["format"] not in VOLUME_FLOAT_FORMATS:
            print(json.dumps(dict(index=index, shape=shape, blocked=(
                f"format {d['format']} is not one of the float16 volume formats this tool decodes "
                "(10/54)")), indent=1))
            return 2
        tiled = _read_range_or_block(pool, d["base"], layout["size"], cache, bcpack_mode, index,
                                     shape, history)
        if tiled is None:
            return 2
        linear_3d = detile_volume(layout, tiled)
        vox_3d = _decode_volume_voxels(d["format"], linear_3d, d["width"], d["height"], d["depth"])
        z_diff_3d = _volume_z_diff(vox_3d, d["width"], d["height"], d["depth"])
        # Negative control: treat the buffer as stacked 2D SW_4KB_S planes.
        lay_2d = compact_surface_layout(d["width"], d["height"], 1, layout["element_bytes"], 1, 4096)
        mip_2d = lay_2d["mips"][0]
        plane_bytes = lay_2d["size"]
        buf_2d = bytearray()
        for z in range(d["depth"]):
            off = z * plane_bytes
            if off + plane_bytes <= len(tiled):
                buf_2d += detile(lay_2d, mip_2d, tiled[off:off + plane_bytes])
            else:
                buf_2d += bytes(d["width"] * d["height"] * layout["element_bytes"])
        vox_2d = _decode_volume_voxels(d["format"], bytes(buf_2d), d["width"], d["height"], d["depth"])
        z_diff_2d = _volume_z_diff(vox_2d, d["width"], d["height"], d["depth"])
        result = dict(index=index, shape=shape, width=d["width"], height=d["height"],
                      depth=d["depth"], format=d["format"], mips=d["mips"], tile=layout["tile"],
                      block_d=layout["block_d"], padded_d=layout["padded_d"],
                      volume_3d_z_diff=round(z_diff_3d, 6) if z_diff_3d is not None else None,
                      volume_2d_control_z_diff=round(z_diff_2d, 6) if z_diff_2d is not None else None,
                      full_chain=a.get("full_chain"))
        print(json.dumps(result, indent=1))
        ok = (z_diff_3d is not None and z_diff_2d is not None and
              z_diff_3d < 0.5 * z_diff_2d)
        return 0 if ok else 1

    if shape == "2d_array":
        tiled = _read_range_or_block(pool, d["base"], layout["size"], cache, bcpack_mode, index,
                                     shape, history)
        if tiled is None:
            return 2
        per_slice_max = []
        all_errs = []
        for s in range(d["depth"]):
            means, errs = _check_mip_chain_means(
                layout, d["format"],
                lambda m, sl=s: tiled[m["offset"] + sl * m["slice_stride"]:
                                      m["offset"] + sl * m["slice_stride"] + m["region"]])
            if all(m is None for m in means):
                print(json.dumps(dict(index=index, shape=shape, blocked=(
                    f"format {d['format']} is not one of the BC formats this tool decodes "
                    "(71/72/77/78/80/83)")), indent=1))
                return 2
            per_slice_max.append(max((e for e in errs if e is not None), default=None))
            all_errs.extend(errs)
        # Negative control: interpret the same allocation as slice-major.
        single = surface_layout(d["width"], d["height"], d["format"], d["mips"], layout["tile"])
        ctrl_errs = []
        for s in range(d["depth"]):
            base_s = s * layout["slice_size"]
            _, cerrs = _check_mip_chain_means(
                single, d["format"],
                lambda m, b0=base_s: tiled[b0 + m["offset"]:b0 + m["offset"] + m["region"]])
            ctrl_errs.extend(e for e in cerrs if e is not None)
        result = dict(index=index, shape=shape, width=d["width"], height=d["height"],
                      depth=d["depth"], format=d["format"], mips=d["mips"],
                      first_tail=layout["first_tail"], tile=layout["tile"],
                      per_slice_max_error=per_slice_max,
                      max_error=max((e for e in all_errs if e is not None), default=None),
                      slice_major_control_max_error=max(ctrl_errs, default=None),
                      full_chain=a.get("full_chain"))
        print(json.dumps(result, indent=1))
        return 0 if all(e is not None and e <= 6 for e in all_errs) else 1

    if shape == "cubemap":
        tiled = _read_range_or_block(pool, d["base"] + layout["data_offset"], layout["full_bytes"],
                                     cache, bcpack_mode, index, shape, history)
        if tiled is None:
            return 2
        per_face_max = []
        all_errs = []
        face0_means = None
        for face in range(6):
            fbase = face * layout["face_size"]
            means, errs = _check_mip_chain_means(
                layout, d["format"],
                lambda m, b0=fbase: tiled[b0 + m["offset"]:b0 + m["offset"] + m["region"]])
            if all(m is None for m in means):
                print(json.dumps(dict(index=index, shape=shape, blocked=(
                    f"format {d['format']} is not one of the BC formats this tool decodes "
                    "(71/72/77/78/80/83)")), indent=1))
                return 2
            if face == 0:
                face0_means = means
            per_face_max.append(max((e for e in errs if e is not None), default=None))
            all_errs.extend(errs)
        control = None
        if 0 < layout["first_tail"] < d["mips"] and face0_means and face0_means[layout["first_tail"] - 1] is not None:
            tm = layout["mips"][layout["first_tail"]]
            bad = dict(tm, tile_x=0, tile_y=0)
            data = detile(layout, bad, tiled[:layout["tile"]])
            px = decode_pixels(d["format"], data, tm["blocks_w"], tm["blocks_h"])
            if px is not None:
                pm = layout["mips"][layout["first_tail"] - 1]
                control = round(mean_abs_error(
                    downsample2(face0_means[layout["first_tail"] - 1], pm["blocks_w"], pm["blocks_h"]),
                    block_means(px, tm["blocks_w"], tm["blocks_h"], tm["pixels_w"], tm["pixels_h"])), 2)
        result = dict(index=index, shape=shape, width=d["width"], height=d["height"],
                      depth=6, format=d["format"], mips=d["mips"], non_tail=d["non_tail"],
                      snapshots=layout["snapshots"], data_offset=layout["data_offset"],
                      first_tail=layout["first_tail"], tile=layout["tile"],
                      per_face_max_error=per_face_max,
                      max_error=max((e for e in all_errs if e is not None), default=None),
                      tail_origin_control=control, full_chain=a.get("full_chain"))
        print(json.dumps(result, indent=1))
        return 0 if all(e is not None and e <= 6 for e in all_errs) else 1

    tiled = _read_range_or_block(pool, d["base"], layout["size"], cache, bcpack_mode, index,
                                 bcpack_history=history)
    if tiled is None:
        return 2
    means, errs = _check_mip_chain_means(
        layout, d["format"],
        lambda m: tiled[m["offset"]:m["offset"] + m["region"]])
    if all(m is None for m in means):
        print(json.dumps(dict(index=index, blocked=(
            f"format {d['format']} is not one of the BC formats this tool decodes "
            "(71/72/77/78/80/83)")), indent=1))
        return 2
    control = None
    if 0 < layout["first_tail"] < d["mips"] and means[layout["first_tail"] - 1] is not None:
        tm = layout["mips"][layout["first_tail"]]
        bad = dict(tm, tile_x=0, tile_y=0)
        data = detile(layout, bad, tiled[:layout["tile"]])
        px = decode_pixels(d["format"], data, tm["blocks_w"], tm["blocks_h"])
        if px is not None:
            pm = layout["mips"][layout["first_tail"] - 1]
            control = round(mean_abs_error(
                downsample2(means[layout["first_tail"] - 1], pm["blocks_w"], pm["blocks_h"]),
                block_means(px, tm["blocks_w"], tm["blocks_h"], tm["pixels_w"], tm["pixels_h"])), 2)
    result = dict(index=index, width=d["width"], height=d["height"], format=d["format"],
                  mips=d["mips"], non_tail=d["non_tail"], first_tail=layout["first_tail"],
                  tile=layout["tile"], chain_error=errs, max_error=max(
                      (e for e in errs if e is not None), default=None),
                  tail_origin_control=control, full_chain=a.get("full_chain"))
    print(json.dumps(result, indent=1))
    return 0 if all(e is not None and e <= 6 for e in errs) else 1


def dds_bytes(width, height, fmt, mips, linear, payload,
              depth=1, array_size=1, is_cube=False, is_volume=False):
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    flags = 0x1007 | (0x80000 if fmt in BC_FORMATS else 0x8)
    if mips > 1:
        flags |= 0x20000
    if is_volume:
        flags |= 0x800000
    caps = 0x1000
    if mips > 1:
        caps |= 0x400008
    if is_cube or is_volume or array_size > 1:
        caps |= 0x8
    caps2 = 0
    if is_cube:
        caps2 |= 0xFE00
    if is_volume:
        caps2 |= 0x200000
    struct.pack_into("<IIIIIII", hdr, 4, 124, flags, height, width, linear,
                     depth if is_volume else 0, mips)
    struct.pack_into("<II4s", hdr, 76, 32, 4, b"DX10")
    struct.pack_into("<II", hdr, 108, caps, caps2)
    dim = 4 if is_volume else 3
    misc = 0x4 if is_cube else 0
    dx10_array = 1 if (is_cube or is_volume) else array_size
    return bytes(hdr) + struct.pack("<IIIII", fmt, dim, misc, dx10_array, 0) + payload


def export(pool, index, out_path, mips=None, force=False, *, allow_provisional=False, history=None):
    a = analyze(pool, index)
    if "layout" not in a or "available" not in a:
        print(f"texture {index}: {a.get('blocked', 'layout unavailable')}", file=sys.stderr)
        return 2
    d = a["descriptor"]
    shape = a.get("shape", "2d")
    if shape != "volume" and d["format"] not in BC_FORMATS:
        print(f"texture {index}: format {d['format']} is uncompressed; this tool does not "
              "validate uncompressed 2D tiling, so it will not write a DDS", file=sys.stderr)
        return 2
    if shape == "volume" and d["format"] not in VOLUME_FLOAT_FORMATS:
        print(f"texture {index}: volume format {d['format']} is not validated for export",
              file=sys.stderr)
        return 2
    if not a["full_chain"]:
        print(f"texture {index}: not every source mip uses a supported codec "
              "(zlib/raw/BCPack BC1/BC3/BC4/BC5/BC6H/BC7)", file=sys.stderr)
        return 2
    count = d["mips"] if mips is None else mips
    if count < 1 or count > d["mips"]:
        print(f"texture {index}: --mips must be 1..{d['mips']}", file=sys.stderr)
        return 2
    layout = a["layout"]
    cache = {}
    bcpack_mode = "provisional" if allow_provisional else "strict"
    payload = bytearray()
    try:
        if shape == "volume":
            tiled = pool.read_range(d["base"], layout["size"], cache,
                                    bcpack_mode=bcpack_mode, bcpack_history=history)
            payload += detile_volume(layout, tiled)
        elif shape == "2d_array":
            for s in range(d["depth"]):
                for mip in layout["mips"][:count]:
                    tiled = pool.read_range(d["base"] + mip["offset"] + s * mip["slice_stride"],
                                            mip["region"], cache,
                                            bcpack_mode=bcpack_mode, bcpack_history=history)
                    payload += detile(layout, mip, tiled)
        elif shape == "cubemap":
            face_base = d["base"] + layout["data_offset"]
            for face in range(6):
                for mip in layout["mips"][:count]:
                    tiled = pool.read_range(face_base + face * layout["face_size"] + mip["offset"],
                                            mip["region"], cache,
                                            bcpack_mode=bcpack_mode, bcpack_history=history)
                    payload += detile(layout, mip, tiled)
        else:
            for mip in layout["mips"][:count]:
                tiled = pool.read_range(d["base"] + mip["offset"], mip["region"], cache,
                                        bcpack_mode=bcpack_mode, bcpack_history=history)
                payload += detile(layout, mip, tiled)
    except BcpackRequired as exc:
        print(f"texture {index}: {exc}", file=sys.stderr)
        return 2
    except bcpack.BcpackProvisionalError as exc:
        print(f"texture {index}: provisional BCPack history required ({exc}); "
              "pass --allow-provisional", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"texture {index}: {exc}", file=sys.stderr)
        return 2
    if 148 + len(payload) > MAX_OUTPUT:
        print("DDS exceeds the 256 MiB output limit", file=sys.stderr)
        return 2
    if os.path.exists(out_path) and not force:
        print(f"{out_path} exists; pass --force to replace it", file=sys.stderr)
        return 2
    top = layout["mips"][0]
    linear = (top["blocks_w"] * top["blocks_h"] * layout["element_bytes"]
              if d["format"] in BC_FORMATS else d["width"] * layout["element_bytes"])
    blob = dds_bytes(
        d["width"], d["height"], d["format"], count, linear, bytes(payload),
        depth=d["depth"] if shape == "volume" else 1,
        array_size=d["depth"] if shape == "2d_array" else 1,
        is_cube=(shape == "cubemap"),
        is_volume=(shape == "volume"),
    )
    with open(out_path, "wb") as f:
        f.write(blob)
    dims = (f"{d['width']}x{d['height']}x{d['depth']}" if shape in ("2d_array", "volume")
            else f"{d['width']}x{d['height']}")
    print(f"texture {index}: {shape} {dims} fmt {d['format']} {count} mips "
          f"({len(blob)} bytes) -> {out_path}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scan", help="aggregate counters over pools")
    ps.add_argument("paths", nargs="+")
    ps.add_argument("--json")
    ps.add_argument("--tuples", action="store_true",
                    help="include the distinct rejected compact-profile tuples")
    pl = sub.add_parser("layout", help="descriptor fields and mip offsets")
    pl.add_argument("pool")
    pl.add_argument("index", type=int)
    pc = sub.add_parser("check", help="decode a chain and report downsample error")
    pc.add_argument("pool")
    pc.add_argument("index", type=int)
    pc.add_argument("--allow-provisional", action="store_true",
                    help="allow unconfirmed built-in BCPack history entries")
    pc.add_argument("--history",
                    help="local JSON file or directory supplying BC6H/BC7 initial history tables")
    pe = sub.add_parser("export", help="write the full chain as DDS")
    pe.add_argument("pool")
    pe.add_argument("index", type=int)
    pe.add_argument("out")
    pe.add_argument("--mips", type=int)
    pe.add_argument("--force", action="store_true")
    pe.add_argument("--allow-provisional", action="store_true",
                    help="allow unconfirmed built-in BCPack history entries")
    pe.add_argument("--history",
                    help="local JSON file or directory supplying BC6H/BC7 initial history tables")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        pools = []
        for p in a.paths:
            pools += find_pools(p)
        try:
            scan_pools(pools, a.json, a.tuples)
        except ValueError as exc:   # a truncated or unsupported pool: name it instead of a traceback
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0
    try:
        pool = Pool(a.pool)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {a.pool}: {exc}", file=sys.stderr)
        return 2
    try:
        if not 0 <= a.index < pool.textures:
            print(f"ERROR: texture {a.index} is out of range: {a.pool} holds {pool.textures}",
                  file=sys.stderr)
            return 2
        if a.cmd == "layout":
            print(json.dumps(describe(pool, a.index), indent=1))
            return 0
        if a.cmd == "check":
            return check(pool, a.index, allow_provisional=a.allow_provisional, history=a.history)
        return export(pool, a.index, a.out, a.mips, a.force,
                      allow_provisional=a.allow_provisional, history=a.history)
    finally:
        pool.close()


if __name__ == "__main__":
    sys.exit(main())
````

## tests/test_bcpack.py

SHA-256 `3033c40b1b2ced9e3973bbee30fe23241952ab410e766351c3a30269aad88520`

````python
"""Tests for tools/bcpack.py, bcpack_tables.py and bcpack_tables_bptc.py.

Builds genuine BCPack rANS streams from scratch with a self-contained test
encoder — no game files or texture bytes are used.

    python -I tests/test_bcpack.py
"""
import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bcpack  # noqa: E402
import bcpack_tables as tables  # noqa: E402
import bcpack_tables_bptc as bptc  # noqa: E402


# --- Synthetic BCPack rANS encoder (test helper only) ----------------------

def _zig(v):
    """Inverse of bcpack._unzig for signed integer deltas."""
    return (-2 * v - 1) if v < 0 else (2 * v)


def _deint_n(v, n):
    """Inverse of bcpack._inter: split 2n-bit integer into two n-bit halves."""
    a = b = 0
    for k in range(n):
        a |= ((v >> (2 * k)) & 1) << k
        b |= ((v >> (2 * k + 1)) & 1) << k
    return a, b


def _deint4(v):
    """Inverse of bcpack._inter8: split 8-bit integer into two 4-bit nibbles."""
    return _deint_n(v, 4)


def _pack_ix_pair(d0, d1, y):
    """Inverse of the BC6H/BC7 row index de-interleave for pixels (2k, 2k+1) on row y."""
    return bcpack._inter(d1, d0, 4) if y < 3 else bcpack._inter(d0, d1, 4)


def _encode_rans_syms(syms, model, x):
    """Reverse-encode `syms` starting from end state `x`, returning `(new_x, bytes_reversed)`."""
    buf = []
    for s in reversed(syms):
        p = s.bit_length()
        f = model.freq[p]
        c = model.base[p] + f * (s - (0 if p == 0 else 1 << (p - 1)))
        if c == 0:
            f, c = f - 1, 1
        limit = f << 16
        while x >= limit:
            buf.append(x & 0xFF)
            x >>= 8
        q_div, r_mod = divmod(x, f)
        x = (q_div << 16) + c + r_mod
    return x, buf


def _make_hdr(default_w, w, q, flush, n):
    z = default_w - w
    assert 0 <= z <= 3 and n >= 1
    if n <= 256:
        return [((z & 3) << 6) | ((1 if flush else 0) << 4) | (q & 15), n - 1]
    n2 = n - 257
    return [
        ((z & 3) << 6) | (1 << 5) | ((1 if flush else 0) << 4) | (q & 15),
        n2 & 0xFF,
        (n2 >> 8) & 0xFF,
    ]


def _encode_fragment(syms, default_w, w, q, *, flush=True, strip_zeros=True):
    """Encode `syms` into one standalone flush fragment (header + rANS payload)."""
    assert flush
    model = bcpack._get_model(w, q)
    assert model is not None
    x, buf = _encode_rans_syms(syms, model, bcpack.RANS_L)
    payload = [(x >> 24) & 0xFF, (x >> 16) & 0xFF, (x >> 8) & 0xFF, x & 0xFF] + list(reversed(buf))
    if strip_zeros:
        stripped = 0
        while len(payload) > 1 and payload[-1] == 0 and stripped < bcpack.MAX_VIRTUAL_ZEROS:
            payload.pop()
            stripped += 1
    return bytes(_make_hdr(default_w, w, q, True, len(payload)) + payload), 0


def _encode_lane_stream(fragments, default_w):
    """Chain one or more `(syms, w, q, flush)` fragments for a single lane.

    The final fragment must have `flush=True`. For a non-flush fragment followed
    by another fragment, the boundary state is shifted below `RANS_L` so the
    decoder finishes fragment `i` at `st < RANS_L` and renormalizes from fragment `i+1`.
    """
    encoded = [None] * len(fragments)
    x = bcpack.RANS_L
    for idx in range(len(fragments) - 1, -1, -1):
        syms, w, q, flush = fragments[idx]
        model = bcpack._get_model(w, q)
        assert model is not None
        if flush:
            x = bcpack.RANS_L
        x, buf = _encode_rans_syms(syms, model, x)
        prev_flush = True if idx == 0 else fragments[idx - 1][3]
        if prev_flush:
            # This fragment starts from state 0: prepend all 4 initial state bytes.
            payload = [(x >> 24) & 0xFF, (x >> 16) & 0xFF, (x >> 8) & 0xFF, x & 0xFF] + list(reversed(buf))
            if flush:
                stripped = 0
                while len(payload) > 1 and payload[-1] == 0 and stripped < bcpack.MAX_VIRTUAL_ZEROS:
                    payload.pop()
                    stripped += 1
        else:
            # Previous fragment is non-flush: emit renormalization bytes into this
            # fragment until `x < RANS_L` so the previous fragment hands off `x < RANS_L`.
            while x >= bcpack.RANS_L:
                buf.append(x & 0xFF)
                x >>= 8
            payload = list(reversed(buf))
        encoded[idx] = bytes(_make_hdr(default_w, w, q, flush, len(payload)) + payload)
    return b"".join(encoded)


def interleave_lanes(lane_streams, widths, nsym):
    """Interleave per-lane byte streams according to the BCPack 8-byte/cycle scheduler."""
    nl = len(widths)
    HDR0, HDR1, HDR2, PROC = 0, 1, 2, 3
    L = bcpack.RANS_L
    ctrl = [HDR0] * nl
    out_rem = [nsym] * nl
    w = [0] * nl
    q = [0] * nl
    h3 = [0] * nl
    flush = [0] * nl
    done = [nsym <= 0] * nl
    full = [False] * nl
    held = [False] * nl
    vz = [0] * nl
    inbuf = [0] * nl
    sym = [0] * nl
    in_rem = [0] * nl
    p0 = [0] * nl
    p1 = [0] * nl
    model = [None] * nl
    slotfull = [False] * nl
    stall = [False] * nl
    lpos = [0] * nl
    interleaved = bytearray()
    max_cycles = max(1000, nsym * 64 + sum(len(s) for s in lane_streams) * 8)

    for _ in range(max_cycles):
        if all(done[i] and not slotfull[i] for i in range(nl)):
            for i in range(nl):
                assert lpos[i] == len(lane_streams[i]), f"lane {i} left {len(lane_streams[i]) - lpos[i]} bytes"
            return bytes(interleaved)
        left = bcpack.PREFETCH_BUDGET
        for i in range(nl):
            if done[i] or (held[i] and slotfull[i]):
                stall[i] = True
                continue
            stall[i] = False
            if ctrl[i] == PROC:
                p0[i] = model[i].advance(sym[i], p1[i]) if held[i] else p1[i]
            if not full[i] and (ctrl[i] != PROC or in_rem[i] > 0):
                if left == 0:
                    stall[i] = True
                    continue
                b = lane_streams[i][lpos[i]]
                lpos[i] += 1
                interleaved.append(b)
                inbuf[i] = b
                full[i] = True
                left -= 1
            if held[i]:
                slotfull[i] = True
                held[i] = False
        for i in range(nl):
            if done[i] or stall[i]:
                continue
            c = ctrl[i]
            if c == HDR0:
                if not full[i]:
                    continue
                h = inbuf[i]
                q[i] = h & 15
                flush[i] = (h >> 4) & 1
                h3[i] = (h >> 5) & 1
                w[i] = widths[i] - (h >> 6)
                full[i] = False
                ctrl[i] = HDR1
                vz[i] = 0
            elif c == HDR1:
                if not full[i]:
                    continue
                full[i] = False
                model[i] = bcpack._get_model(w[i], q[i])
                if h3[i]:
                    in_rem[i] = inbuf[i]
                    ctrl[i] = HDR2
                else:
                    in_rem[i] = inbuf[i] + 1
                    ctrl[i] = PROC
            elif c == HDR2:
                if not full[i]:
                    continue
                in_rem[i] = ((inbuf[i] << 8) | (in_rem[i] & 0xFF)) + 257
                ctrl[i] = PROC
                full[i] = False
            else:
                st = p0[i]
                if st < L:
                    if in_rem[i] > 0:
                        if full[i]:
                            st = (st << 8) | inbuf[i]
                            in_rem[i] -= 1
                            full[i] = False
                            if in_rem[i] == 0 and flush[i]:
                                while st < L and st != 0 and vz[i] < bcpack.MAX_VIRTUAL_ZEROS:
                                    st <<= 8
                                    vz[i] += 1
                    elif flush[i]:
                        while st < L and st != 0 and vz[i] < bcpack.MAX_VIRTUAL_ZEROS:
                            st <<= 8
                            vz[i] += 1
                    else:
                        p1[i] = st
                        if out_rem[i] > 0:
                            ctrl[i] = HDR0
                        else:
                            done[i] = True
                        continue
                nxt = st > L and out_rem[i] > 0
                if nxt:
                    sym[i] = model[i].lookup(st & 0xFFFF)
                    out_rem[i] -= 1
                held[i] = nxt
                p1[i] = st
                if in_rem[i] == 0:
                    if flush[i]:
                        if st == L:
                            if out_rem[i] > 0:
                                ctrl[i] = HDR0
                                p0[i] = 0
                                p1[i] = 0
                            else:
                                done[i] = True
                    elif out_rem[i] == 0 and not nxt:
                        done[i] = True
        ready = True
        anyfull = False
        for i in range(nl):
            if slotfull[i]:
                anyfull = True
            elif not (done[i] and not held[i]):
                ready = False
                break
        if ready and anyfull:
            for i in range(nl):
                slotfull[i] = False
        for i in range(nl):
            if done[i] and held[i] and not slotfull[i]:
                slotfull[i] = True
                held[i] = False
    raise AssertionError("interleave_lanes exceeded max_cycles")


def encode_lanes(lanes, codec, *, q=0):
    """Encode per-lane symbol lists into a complete BCPack chunk."""
    widths = bcpack.LANE_WIDTHS[codec]
    nsym = len(lanes[0])
    streams = []
    for i, (syms, dw) in enumerate(zip(lanes, widths)):
        qi = q[i] if isinstance(q, (list, tuple)) else q
        frag, _ = _encode_fragment(syms, dw, dw, qi, flush=True)
        streams.append(frag)
    return interleave_lanes(streams, widths, nsym)


def encode_bc1_blocks(blocks, *, ref_dists=None):
    """Encode raw BC1 blocks (8 bytes each) into a valid codec-1 BCPack chunk."""
    n = len(blocks) // 8
    inv_quad = {v: i for i, v in enumerate(tables.BC1_QUADRANT)}
    mods = (32, 64, 32, 32, 64, 32)
    lanes = [[] for _ in range(12)]
    hist = []
    for i in range(n):
        c0, c1, r0, r1, r2, r3 = struct.unpack_from("<HHBBBB", blocks, i * 8)
        e = ((c0 >> 11) & 31, (c0 >> 5) & 63, c0 & 31,
             (c1 >> 11) & 31, (c1 >> 5) & 63, c1 & 31)
        d = 0 if ref_dists is None else ref_dists[i]
        if d == 0:
            base = (0, 0, 0, 0, 0, 0)
        elif i - d >= 0:
            base = hist[i - d]
        else:
            entry = 256 + i - d
            base = tables.BC1_HISTORY_CONFIRMED.get(entry) or tables.BC1_HISTORY_PROVISIONAL.get(entry) or (0, 0, 0, 0, 0, 0)
        signed_d = d if d < 128 else d - 256
        lanes[0].append(_zig(signed_d))
        lanes[1].append(0)
        for k in range(6):
            delta = (e[k] - base[k]) % mods[k]
            if delta >= mods[k] // 2:
                delta -= mods[k]
            lanes[2 + k].append(_zig(delta))
        hist.append(e)
        qa = (r0 & 15) | ((r1 & 15) << 4)
        qb = (r0 >> 4) | ((r1 >> 4) << 4)
        qc = (r2 & 15) | ((r3 & 15) << 4)
        qd = (r2 >> 4) | ((r3 >> 4) << 4)
        lanes[8].append(inv_quad[qa])
        lanes[9].append(inv_quad[qb])
        lanes[10].append(inv_quad[qc])
        lanes[11].append(inv_quad[qd])
    return encode_lanes(lanes, 1)


# --- Unit tests ------------------------------------------------------------

class ProbTablesTest(unittest.TestCase):
    def test_all_160_tables_valid_and_invertible(self):
        self.assertEqual(len(tables.PROB_TABLES), 160)
        for w in range(1, 11):
            for q in range(16):
                m = bcpack._get_model(w, q)
                self.assertIsNotNone(m)
                # Verify boundary symbols (0, 1, mid, max) invert cleanly.
                for s in {0, 1, (1 << (w - 1)), (1 << w) - 1}:
                    p = s.bit_length()
                    f = m.freq[p]
                    c = m.base[p] + f * (s - (0 if p == 0 else 1 << (p - 1)))
                    if c == 0:
                        f, c = f - 1, 1
                    x = (256 << 16) + c
                    self.assertEqual(m.lookup(x & 0xFFFF), s)
                    self.assertEqual(m.advance(s, x), 256 * f)


class EntropyLayerTest(unittest.TestCase):
    def test_round_trip_12_and_16_lanes(self):
        for codec in (1, 3, 4, 5, 6, 7):
            widths = bcpack.LANE_WIDTHS[codec]
            nsym = 24
            lanes = [[((i * 13 + j * 7) & ((1 << dw) - 1)) for j in range(nsym)]
                     for i, dw in enumerate(widths)]
            qs = [(i * 3) % 15 for i in range(len(widths))]
            raw = encode_lanes(lanes, codec, q=qs)
            decoded, used = bcpack.decode_lanes(raw + b"\x00\x00\x00", codec, nsym * 8)
            self.assertEqual(used, len(raw))
            self.assertEqual(decoded, lanes)

    def test_multi_fragment_flush_and_non_flush_and_3byte_header(self):
        codec = 1
        widths = bcpack.LANE_WIDTHS[codec]
        # 400 symbols forces a >256-byte fragment (3-byte header, h3=1) on 8-bit lanes.
        nsym = 400
        lanes = [[((i * 29 + j * 17) & ((1 << dw) - 1)) for j in range(nsym)]
                 for i, dw in enumerate(widths)]
        streams = []
        for i, (syms, dw) in enumerate(zip(lanes, widths)):
            if i == 0:
                # Two flush fragments with reduced width on the second half.
                s1 = [x & 0x3F for x in syms[:100]]
                s2 = [x & 0x1F for x in syms[100:]]
                lanes[0] = s1 + s2
                streams.append(_encode_lane_stream([
                    (s1, dw - 2, 2, True),
                    (s2, dw - 3, 5, True),
                ], dw))
            elif i == 2:
                # Chained non-flush -> flush fragments with a model change mid-stream.
                streams.append(_encode_lane_stream([
                    (syms[:150], dw, 1, False),
                    (syms[150:], dw, 4, True),
                ], dw))
            else:
                # Single large flush fragment (3-byte header on 8-bit lanes).
                streams.append(_encode_lane_stream([(syms, dw, 0, True)], dw))
        raw = interleave_lanes(streams, widths, nsym)
        decoded, used = bcpack.decode_lanes(raw, codec, nsym * 8)
        self.assertEqual(used, len(raw))
        self.assertEqual(decoded, lanes)

    def test_rejects_corrupt_and_trailing_data(self):
        lanes = [[0] * 8 for _ in range(12)]
        raw = encode_lanes(lanes, 1)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode_lanes(raw + b"\x01", 1, 64)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode_lanes(raw[:-2], 1, 64)
        flipped = bytearray(raw)
        flipped[-1] ^= 0xFF
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode_lanes(bytes(flipped), 1, 64)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode_lanes(raw, 99, 64)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode_lanes(raw, 1, 60)

    def test_unsupported_codec_rebuild_raises(self):
        # Codec 2 (BC2) is unused in the corpus and has no lane/block decoder.
        with self.assertRaises(bcpack.BcpackUnsupportedCodec):
            bcpack.decode(b"", 2, 16)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode_lanes(b"", 2, 16)


class BlockRebuildTest(unittest.TestCase):
    def test_bc1_confirmed_and_provisional_history(self):
        # Block 0: d=0 (zero base); Block 1: dynamic ref to block 0 (d=1);
        # Block 2: confirmed built-in preset 1 (256 + 2 - d == 1 => d=257? no, 256+2-255=3, use entry 255 -> d=3).
        blocks = b"".join([
            struct.pack("<HHBBBB", 0xF800, 0x07E0, 0x12, 0x34, 0x56, 0x78),
            struct.pack("<HHBBBB", 0xF81F, 0x001F, 0xAA, 0xBB, 0xCC, 0xDD),
            struct.pack("<HHBBBB", 0xFFFF, 0x0000, 0x00, 0x55, 0xAA, 0xFF),
        ])
        # Block 2 with d=3 -> 256 + 2 - 3 = 255 (confirmed in BC1_HISTORY_CONFIRMED).
        self.assertIn(255, tables.BC1_HISTORY_CONFIRMED)
        raw = encode_bc1_blocks(blocks, ref_dists=[0, 1, 3])
        out, prov = bcpack.decode_with_info(raw, 1, len(blocks))
        self.assertEqual(out, blocks)
        self.assertEqual(prov, set())

        # Reference provisional entry 6 from block 0: 256 + 0 - d = 6 => d = 250.
        self.assertIn(6, tables.BC1_HISTORY_PROVISIONAL)
        raw_prov = encode_bc1_blocks(blocks[:8], ref_dists=[250])
        with self.assertRaises(bcpack.BcpackProvisionalError):
            bcpack.decode(raw_prov, 1, 8)
        out_p, prov_p = bcpack.decode_with_info(raw_prov, 1, 8, allow_provisional=True)
        self.assertEqual(out_p, blocks[:8])
        self.assertEqual(prov_p, {"BC1 history 6"})

    def test_bc4_round_trip(self):
        inv_pair = {p: i for i, p in enumerate(tables.BC4_PAIR)}
        # Build 2 BC4 blocks: block 0 uses d=0 (base 128,128), block 1 refs block 0 (d=1).
        b0_bits = sum(((r + p) & 7) << (3 * (4 * r + p)) for r in range(4) for p in range(4))
        b1_bits = sum(((7 - r - p) & 7) << (3 * (4 * r + p)) for r in range(4) for p in range(4))
        expected = (
            bytes([130, 120]) + b0_bits.to_bytes(6, "little") +
            bytes([140, 110]) + b1_bits.to_bytes(6, "little")
        )
        lanes = [[] for _ in range(12)]
        for i, (d, base, (a0, a1), bits) in enumerate([
            (0, (128, 128), (130, 120), b0_bits),
            (1, (130, 120), (140, 110), b1_bits),
        ]):
            lanes[0].append(_zig(d))
            lanes[1].append(0)
            lanes[2].append(_zig(a0 - base[0]))
            lanes[3].append(_zig(a1 - base[1]))
            for r in range(4):
                row = (bits >> (12 * r)) & 0xFFF
                lanes[4 + 2 * r].append(inv_pair[(row & 7, (row >> 3) & 7)])
                lanes[4 + 2 * r + 1].append(inv_pair[((row >> 6) & 7, (row >> 9) & 7)])
        raw = encode_lanes(lanes, 4)
        self.assertEqual(bcpack.decode(raw, 4, len(expected)), expected)

        # Provisional BC4 history entry (entry 25 -> block 0 uses d = 231).
        self.assertIn(25, tables.BC4_HISTORY_PROVISIONAL)
        prov_a0, prov_a1 = tables.BC4_HISTORY_PROVISIONAL[25]
        lanes_p = [[_zig(231 - 256)], [0], [0], [0]] + [[0]] * 8
        raw_p = encode_lanes(lanes_p, 4)
        with self.assertRaises(bcpack.BcpackProvisionalError):
            bcpack.decode(raw_p, 4, 8)
        out_p, info_p = bcpack.decode_with_info(raw_p, 4, 8, allow_provisional=True)
        self.assertEqual((out_p[0], out_p[1]), (prov_a0, prov_a1))
        self.assertEqual(info_p, {"BC4 history 25"})

    def test_bc5_round_trip(self):
        inv_pair = {p: i for i, p in enumerate(tables.BC5_PAIR)}
        # Block 0 uses confirmed BC5 entry if present, plus block 1 dynamic ref.
        confirmed_entry = next(iter(sorted(tables.BC5_HISTORY_CONFIRMED)))
        base0 = tables.BC5_HISTORY_CONFIRMED[confirmed_entry]
        d0 = 256 - confirmed_entry  # block 0: 256 + 0 - d0 == confirmed_entry
        e0 = ((base0[0] + 2) & 255, (base0[1] - 3) & 255, (base0[2] + 1) & 255, (base0[3] - 1) & 255)
        e1 = ((e0[0] + 5) & 255, (e0[1] - 4) & 255, (e0[2] + 3) & 255, (e0[3] + 2) & 255)
        bits = [
            (0x0123456789AB, 0xFEDCBA987654),
            (0x112233445566, 0x778899AABBCC),
        ]
        expected = bytearray()
        for e, (br, bg) in zip((e0, e1), bits):
            expected += bytes([e[0], e[1]]) + br.to_bytes(6, "little")
            expected += bytes([e[2], e[3]]) + bg.to_bytes(6, "little")
        lanes = [[] for _ in range(12)]
        for d, base, e, (br, bg) in ((d0, base0, e0, bits[0]), (1, e0, e1, bits[1])):
            sd = d if d < 128 else d - 256
            da, db = _deint4(_zig(sd))
            lanes[0].extend([da, db])
            lanes[1].extend([0, 0])
            for lane_idx, (c_a, c_b, b_a, b_b) in ((2, (e[0], e[1], base[0], base[1])),
                                                   (3, (e[2], e[3], base[2], base[3]))):
                d_a = (c_a - b_a + 128) % 256 - 128
                d_b = (c_b - b_b + 128) % 256 - 128
                lanes[lane_idx].extend([_zig(d_a), _zig(d_b)])
            for ch, bval in enumerate((br, bg)):
                for r in range(4):
                    row = (bval >> (12 * r)) & 0xFFF
                    lanes[4 + 4 * ch + r].extend([
                        inv_pair[(row & 7, (row >> 3) & 7)],
                        inv_pair[((row >> 6) & 7, (row >> 9) & 7)],
                    ])
        raw = encode_lanes(lanes, 5)
        out, prov = bcpack.decode_with_info(raw, 5, len(expected))
        self.assertEqual(out, bytes(expected))
        self.assertEqual(prov, set())

    def test_bc3_round_trip(self):
        inv_pair = {p: i for i, p in enumerate(tables.BC3_ALPHA_PAIR)}
        inv_quad = {v: i for i, v in enumerate(tables.BC3_COLOUR_QUADRANT)}
        # Block 0 with d=0: base is (128, 128, 0, 0, 0, 0, 0, 0).
        a0, a1 = 135, 120
        abits = 0x0123456789AB
        c0 = (5 << 11) | (10 << 5) | 3
        c1 = (2 << 11) | (6 << 5) | 1
        r0, r1, r2, r3 = 0x12, 0x34, 0x56, 0x78
        expected = bytes([a0, a1]) + abits.to_bytes(6, "little") + struct.pack("<HHBBBB", c0, c1, r0, r1, r2, r3)
        lanes = [[] for _ in range(12)]
        lanes[0].extend([0, 0])
        lanes[1].extend([0, 0])
        lanes[2].extend([_zig(a0 - 128), _zig(a1 - 128)])
        for r in range(4):
            row = (abits >> (12 * r)) & 0xFFF
            lanes[3 + r].extend([
                inv_pair[(row & 7, (row >> 3) & 7)],
                inv_pair[((row >> 6) & 7, (row >> 9) & 7)],
            ])
        lanes[7].extend([_zig(5), _zig(2)])
        lanes[8].extend([_zig(10), _zig(6)])
        lanes[9].extend([_zig(3), _zig(1)])
        qa = (r0 & 15) | ((r1 & 15) << 4)
        qb = (r0 >> 4) | ((r1 >> 4) << 4)
        qc = (r2 & 15) | ((r3 & 15) << 4)
        qd = (r2 >> 4) | ((r3 >> 4) << 4)
        lanes[10].extend([inv_quad[qa], inv_quad[qb]])
        lanes[11].extend([inv_quad[qc], inv_quad[qd]])
        raw = encode_lanes(lanes, 3)
        out, prov = bcpack.decode_with_info(raw, 3, len(expected))
        self.assertEqual(out, expected)
        self.assertEqual(prov, set())

    def _signed_mod_delta(self, target, ref, bits):
        mod = 1 << bits
        d = (target - ref) % mod
        if d >= mod // 2:
            d -= mod
        return d

    def _bc7_sig_pair(self, table, mode, part=0, rot=0, isel=0):
        rank = table["config"].index((mode, part, rot, isel))
        idx = table["rank_of"].index(rank)
        return divmod(idx, 16)

    def test_bc6h_round_trip_and_provisional(self):
        # 3-block synthetic BC6H stream exercising:
        #   block 0: mode 1 (2-region, part=5, di=0, de=0)
        #   block 1: mode 13 (1-region, bit 10/11 swap, dynamic ref di=1, de=1)
        #   block 2: mode 14 (1-region, bit 10..15 reverse, dynamic ref di=1, de=1)
        specs = [
            (1, 5, 0, 0,
             [(0x123, 0x05, 0x11, 0x0A), (0x2A5, 0x14, 0x07, 0x19), (0x0F1, 0x0C, 0x13, 0x04)],
             [2, 5, 7, 1, 3, 6, 4, 2, 0, 3, 2, 5, 7, 1, 4, 0]),
            (13, 0, 1, 1,
             [(0xA55, 0x33, 0, 0), (0x5AA, 0x81, 0, 0), (0xC12, 0x47, 0, 0)],
             [5, 12, 9, 3, 14, 7, 1, 8, 11, 4, 6, 15, 2, 10, 13, 0]),
            (14, 0, 1, 1,
             [(0xB419, 0x07, 0, 0), (0x9C23, 0x0B, 0, 0), (0x4D05, 0x02, 0, 0)],
             [3, 14, 8, 6, 1, 12, 9, 4, 15, 2, 7, 10, 5, 13, 0, 11]),
        ]
        # Ensure anchor2[5] has top bit 0 for block 0.
        a2_5 = bptc.BC7_ANCHOR2[5]
        specs[0][5][a2_5] &= 3

        lanes = [[] for _ in range(16)]
        st_e, st_i = [], []
        expected = bytearray()
        for idx, (mode, part, di, de, eps, ixs) in enumerate(specs):
            code = bcpack._BC6H_CODE[mode]
            trans, base, deltas, reg = bcpack._BC6H_INFO[code]
            eref = bcpack._BC6H_NONE_E if de == 0 else st_e[idx - de]
            iref = bcpack._BC6H_NONE_I if di == 0 else st_i[idx - di]
            diff_d = (de - di) % 256
            if diff_d >= 128:
                diff_d -= 256
            l0a, l0b = _deint4(_zig(diff_d))
            l1a, l1b = _deint4(di)
            lanes[0].extend([l0a, l0b])
            lanes[1].extend([l1a, l1b])
            lanes[15].extend([mode - 1, part])

            w_shift = 16 - base
            f_blk = []
            st_blk = []
            for c in range(3):
                dc = deltas[c]
                sh = 6 - dc if dc < 6 else 0
                mD = (1 << dc) - 1
                w, x, y, z = eps[c]
                r0, r1, r2, r3 = eref[c]
                dz0 = self._signed_mod_delta(w, r0 >> w_shift, base)
                dz1 = self._signed_mod_delta(x, r1 >> (10 - dc), dc)
                dz2 = self._signed_mod_delta(y, r2 >> sh, dc) if reg == 2 else 0
                dz3 = self._signed_mod_delta(z, r3 >> sh, dc) if reg == 2 else 0
                a0, b0 = _deint_n(_zig(dz0), 8)
                a1, b1 = _deint_n(_zig(dz1), 5)
                lanes[2 + c].extend([a0, b0])
                lanes[5 + c].extend([a1, b1])
                lanes[8 + c].extend([_zig(dz2), _zig(dz3)])
                x10 = x << (10 - dc)
                if reg == 2:
                    st_blk.append((w << w_shift, x10, y << sh, z << sh))
                    f_blk.append((bcpack._bc6h_stream_w(mode, w), x, y, z))
                else:
                    v = (w & mD) ^ ((1 << (dc - 1)) if trans == 1 else 0)
                    low_y = (v >> (dc - 6)) if dc >= 6 else (v << sh)
                    st_blk.append((w << w_shift, x10, low_y, x10 >> 4))
                    f_blk.append((bcpack._bc6h_stream_w(mode, w), x, 0, 0))
            st_e.append(tuple(st_blk))

            ibits = 3 if reg == 2 else 4
            ishift = 4 - ibits
            for yy in range(4):
                ds = [_zig(self._signed_mod_delta(ixs[yy * 4 + xx], iref[yy * 4 + xx] >> ishift, ibits))
                      for xx in range(4)]
                lanes[11 + yy].extend([
                    _pack_ix_pair(ds[0], ds[1], yy),
                    _pack_ix_pair(ds[2], ds[3], yy),
                ])
            st_i.append(tuple(v << ishift for v in ixs))

            plan, header = bcpack._bc6h_plan(code)
            acc = code
            for c, q, bit_idx, pos in plan:
                if c < 0:
                    if (part >> bit_idx) & 1:
                        acc |= 1 << pos
                elif (f_blk[c][q] >> bit_idx) & 1:
                    acc |= 1 << pos
            second = bptc.BC7_ANCHOR2[part] if reg == 2 else -1
            at = header
            for p in range(16):
                nb = (ibits - 1) if (p == 0 or p == second) else ibits
                acc |= (ixs[p] & ((1 << nb) - 1)) << at
                at += nb
            expected += acc.to_bytes(16, "little")

        raw = encode_lanes(lanes, 6)
        out, prov = bcpack.decode_with_info(raw, 6, len(expected))
        self.assertEqual(out, bytes(expected))
        self.assertEqual(prov, set())

        # Built-in BC6H history reference (entry k=42, di=de=256-42) with no
        # external history table: strict refuses with --history hint; a 3-block
        # chain exceeding _loose_limit also refuses in provisional mode.
        k_fit = 42
        l1a, l1b = _deint4(256 - k_fit)
        eh_val = ((0x2000, 0x100, 0x08, 0x04), (0x4000, 0x200, 0x0C, 0x08), (0x6000, 0x300, 0x10, 0x0C))
        ih_val = (3, 7, 11, 15, 2, 6, 10, 14, 1, 5, 9, 13, 0, 4, 8, 12)
        d0 = _zig(self._signed_mod_delta(0, ih_val[0], 4))
        lanes_p = [[0, 0] for _ in range(16)]
        lanes_p[1] = [l1a, l1b]
        lanes_p[15] = [10, 0]  # mode 11 (1-region, 4-bit indices)
        lanes_p[11] = [_pack_ix_pair(d0, 0, 0), 0]
        raw_p = encode_lanes(lanes_p, 6)
        with self.assertRaisesRegex(bcpack.BcpackProvisionalError, "--history"):
            bcpack.decode(raw_p, 6, 16)

        # 3-block chain off built-in history exceeds loose limit (max(2, n//1024) == 2).
        lanes_3 = [[0] * 6 for _ in range(16)]
        lanes_3[1][0:2] = [l1a, l1b]
        d_prev_a, d_prev_b = _deint4(1)
        lanes_3[1][2:4] = [d_prev_a, d_prev_b]
        lanes_3[1][4:6] = [d_prev_a, d_prev_b]
        lanes_3[15] = [10, 0, 10, 0, 10, 0]
        raw_3 = encode_lanes(lanes_3, 6)
        with self.assertRaisesRegex(bcpack.BcpackProvisionalError, "--history"):
            bcpack.decode(raw_3, 6, 48, allow_provisional=True)

        # External runtime history JSON: test confirmed (class 3), fitted (class 1),
        # and last-resort (class 2) via combined JSON file and directory layouts.
        k_conf, k_lr = 17, 43
        bc6h_doc = {
            "endpointHistory": {str(k_conf): eh_val, str(k_fit): eh_val, str(k_lr): eh_val},
            "indexHistory": {str(k_conf): list(ih_val), str(k_fit): list(ih_val), str(k_lr): list(ih_val)},
            "endpointClass": {str(k_conf): 3, str(k_fit): 1, str(k_lr): 2},
            "indexClass": {str(k_conf): 3, str(k_fit): 1, str(k_lr): 3},
        }
        with tempfile.TemporaryDirectory() as tmp:
            combined = os.path.join(tmp, "history.json")
            with open(combined, "w", encoding="utf-8") as fh:
                json.dump({"bc6h": bc6h_doc}, fh)
            hist_dir = os.path.join(tmp, "hist_dir")
            os.mkdir(hist_dir)
            with open(os.path.join(hist_dir, "bc6h.json"), "w", encoding="utf-8") as fh:
                json.dump(bc6h_doc, fh)

            # Class 1 (fitted): strict refuses, provisional accepts and tags both.
            with self.assertRaises(bcpack.BcpackProvisionalError):
                bcpack.decode(raw_p, 6, 16, history=combined)
            out_p, prov_p = bcpack.decode_with_info(raw_p, 6, 16, allow_provisional=True, history=combined)
            self.assertEqual(len(out_p), 16)
            self.assertIn(f"BC6H endpoint history {k_fit}", prov_p)
            self.assertIn(f"BC6H index history {k_fit}", prov_p)

            # Class 3 (confirmed): strict accepts via directory path with empty prov set.
            c1a, c1b = _deint4(256 - k_conf)
            lanes_c = [[0, 0] for _ in range(16)]
            lanes_c[1] = [c1a, c1b]
            lanes_c[15] = [10, 0]
            lanes_c[11] = [_pack_ix_pair(d0, 0, 0), 0]
            raw_c = encode_lanes(lanes_c, 6)
            out_c, prov_c = bcpack.decode_with_info(raw_c, 6, 16, history=hist_dir)
            self.assertEqual(out_c, out_p)
            self.assertEqual(prov_c, set())

            # Class 2 (last-resort): strict refuses, provisional labels last-resort.
            r1a, r1b = _deint4(256 - k_lr)
            lanes_lr = [[0, 0] for _ in range(16)]
            lanes_lr[1] = [r1a, r1b]
            lanes_lr[15] = [10, 0]
            lanes_lr[11] = [_pack_ix_pair(d0, 0, 0), 0]
            raw_lr = encode_lanes(lanes_lr, 6)
            with self.assertRaises(bcpack.BcpackProvisionalError):
                bcpack.decode(raw_lr, 6, 16, history=hist_dir)
            _, prov_lr = bcpack.decode_with_info(raw_lr, 6, 16, allow_provisional=True, history=hist_dir)
            self.assertIn(f"BC6H endpoint history {k_lr} (last-resort)", prov_lr)

        # Anchor violation in strict mode (zero built-in refs, anchor 0 = 8) raises BcpackError.
        lanes_bad = [[0, 0] for _ in range(16)]
        lanes_bad[15] = [10, 0]  # mode 11, di=0 => iref[0]=8 => delta 0 leaves anchor bit set!
        raw_bad = encode_lanes(lanes_bad, 6)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode(raw_bad, 6, 16)

    def test_bc7_config_completeness_and_empty_defaults(self):
        # BC7_CONFIG must be a bijection over all 285 valid D3D11 BC7 mode
        # configurations plus the (255, 255, 0, 0) sentinel at rank 285.
        self.assertEqual(len(bptc.BC7_CONFIG), 286)
        self.assertEqual(bptc.BC7_CONFIG[-1], (255, 255, 0, 0))
        expected = (
            {(0, p, 0, 0) for p in range(16)}
            | {(1, p, 0, 0) for p in range(64)}
            | {(2, p, 0, 0) for p in range(64)}
            | {(3, p, 0, 0) for p in range(64)}
            | {(4, 0, rot, isel) for rot in range(4) for isel in range(2)}
            | {(5, 0, rot, 0) for rot in range(4)}
            | {(6, 0, 0, 0)}
            | {(7, p, 0, 0) for p in range(64)}
        )
        self.assertEqual(len(expected), 285)
        self.assertEqual(set(bptc.BC7_CONFIG[:-1]), expected)
        self.assertEqual(len(bptc.BC7_CONFIG_INFERRED), 10)
        for rank in bptc.BC7_CONFIG_INFERRED:
            self.assertTrue(0 <= rank < 285)
            self.assertEqual(bptc.BC7_CONFIG[rank][0], 2)

        # Default history loaders embed no fitted/game-derived history tables.
        _, _, ec, ic = bptc.load_bc6h()
        self.assertEqual(ec, (0,) * 256)
        self.assertEqual(ic, (0,) * 256)
        t7 = bptc.load_bc7()
        self.assertEqual(t7["last_resort"], frozenset())
        self.assertTrue(all(not any(row) for row in t7["history_endpoint_bits"]))
        self.assertTrue(all(not any(row) for row in t7["history_index_bits"]))

    def test_bc7_round_trip_and_provisional(self):
        table = bptc.load_bc7()
        # Block 0: mode 6 (RGBA7777 + per-endpoint p-bits, 4-bit indices), di=0, de=0.
        # Block 1: mode 1 (2 subsets, RGB666 + shared p-bits, 3-bit indices), dynamic di=1, de=1.
        # Block 2: mode 4 (rot=2, isel=1, 2-bit primary + 3-bit secondary indices), di=0, de=0.
        # Block 3: mode 0 all-zero block -> 16 zero bytes.
        s_m6 = self._bc7_sig_pair(table, 6, 0, 0, 0)
        s_m1 = self._bc7_sig_pair(table, 1, 3, 0, 0)
        s_m4 = self._bc7_sig_pair(table, 4, 0, 2, 1)
        s_m0 = self._bc7_sig_pair(table, 0, 0, 0, 0)

        lanes = [[] for _ in range(16)]
        expected = bytearray()

        # --- Block 0: mode 6 ---
        # R (7+1=8 bits, LSB is p-bit), G (7), B (7), A (7).
        ep0 = [((0x65, 0x3A, 0x51, 0x70), (0x92, 0x1F, 0x24, 0x61))]  # R0 p=1, R1 p=0
        ix0 = [3, 10, 15, 2, 7, 12, 4, 9, 14, 1, 6, 11, 5, 8, 13, 0]
        lanes[0].extend([0, 0])
        lanes[1].extend([0, 0])
        lanes[15].extend(list(s_m6))
        for c, ln in enumerate((2, 3, 4, 5)):
            bits = 8 if c == 0 else 7
            lanes[ln].extend([
                _zig(self._signed_mod_delta(ep0[0][0][c], 0, bits)),
                _zig(self._signed_mod_delta(ep0[0][1][c], 0, bits)),
            ])
        for ln in (6, 7, 8, 9, 10):
            lanes[ln].extend([0, 0])
        for y in range(4):
            ds = [_zig(self._signed_mod_delta(ix0[y * 4 + x], 0, 4)) for x in range(4)]
            lanes[11 + y].extend([_pack_ix_pair(ds[0], ds[1], y), _pack_ix_pair(ds[2], ds[3], y)])
        # Pack expected mode-6 block directly from BC7 spec.
        acc = 1 << 6
        pos = 7
        for c in range(4):
            for e in range(2):
                v = ep0[0][e][c] >> 1 if c == 0 else ep0[0][e][c]
                acc |= (v & 0x7F) << pos
                pos += 7
        acc |= (ep0[0][0][0] & 1) << pos
        pos += 1
        acc |= (ep0[0][1][0] & 1) << pos
        pos += 1
        for p in range(16):
            nb = 3 if p == 0 else 4
            acc |= (ix0[p] & ((1 << nb) - 1)) << pos
            pos += nb
        self.assertEqual(pos, 128)
        expected += acc.to_bytes(16, "little")

        # Stored state after block 0 (replicated across subsets 0..2).
        sep0 = [
            ep0[0][0][0], ep0[0][0][1] << 1, ep0[0][0][2] << 1, ep0[0][0][3] << 1,
            ep0[0][1][0], ep0[0][1][1] << 1, ep0[0][1][2] << 1, ep0[0][1][3] << 1,
        ] * 3
        six0 = list(ix0) + [0] * 16

        # --- Block 1: mode 1 (part=3, 2 subsets, shared p-bit, di=1, de=1) ---
        # R has 6+1=7 bits (LSB is shared p-bit per subset!), G/B have 6 bits.
        ep1 = [
            ((0x53, 0x22, 0x15, 0), (0x29, 0x31, 0x0B, 0)),  # sub 0: both R LSB = 1
            ((0x44, 0x12, 0x38, 0), (0x62, 0x05, 0x20, 0)),  # sub 1: both R LSB = 0
        ]
        ix1 = [2, 5, 7, 1, 4, 6, 0, 3, 7, 2, 1, 5, 6, 3, 4, 2]
        a2_3 = table["anchor2"][3]
        ix1[a2_3] &= 3
        l1a, l1b = _deint4(1)
        lanes[0].extend([0, 0])  # de - di = 0 => de = 1
        lanes[1].extend([l1a, l1b])
        lanes[15].extend(list(s_m1))
        for sub, lns in ((0, (2, 3, 4)), (1, (6, 7, 8))):
            for c, ln in enumerate(lns):
                bits = 7 if c == 0 else 6
                sh = 8 - bits
                lanes[ln].extend([
                    _zig(self._signed_mod_delta(ep1[sub][0][c], sep0[sub * 8 + c] >> sh, bits)),
                    _zig(self._signed_mod_delta(ep1[sub][1][c], sep0[sub * 8 + 4 + c] >> sh, bits)),
                ])
        for ln in (5, 9, 10):
            lanes[ln].extend([0, 0])
        for y in range(4):
            ds = [_zig(self._signed_mod_delta(ix1[y * 4 + x], six0[y * 4 + x] >> 1, 3)) for x in range(4)]
            lanes[11 + y].extend([_pack_ix_pair(ds[0], ds[1], y), _pack_ix_pair(ds[2], ds[3], y)])
        acc = (1 << 1) | (3 << 2)
        pos = 8
        for c in range(3):
            for sub in range(2):
                for e in range(2):
                    v = ep1[sub][e][c] >> 1 if c == 0 else ep1[sub][e][c]
                    acc |= (v & 0x3F) << pos
                    pos += 6
        acc |= (ep1[0][0][0] & 1) << pos
        pos += 1
        acc |= (ep1[1][0][0] & 1) << pos
        pos += 1
        p2_3 = table["partition2"][3]
        for p in range(16):
            anchor = p == (0 if p2_3[p] == 0 else a2_3)
            nb = 2 if anchor else 3
            acc |= (ix1[p] & ((1 << nb) - 1)) << pos
            pos += nb
        self.assertEqual(pos, 128)
        expected += acc.to_bytes(16, "little")

        # --- Block 2: mode 4 (rot=2, isel=1, di=0, de=0) ---
        # With rot=2: true channel 1 (G) gets ab=6 bits, true channel 3 (A) gets cb=5 bits.
        ep2 = ((0x15, 0x2B, 0x0C, 0x1A), (0x09, 0x34, 0x1E, 0x07))
        ix2_s1 = [2, 7, 5, 1, 6, 3, 4, 0, 7, 2, 1, 5, 3, 6, 0, 4]  # 3-bit secondary (lanes 11..14)
        ix2_s2 = [1, 3, 2, 0, 2, 1, 3, 0, 3, 2, 1, 0, 1, 2, 3, 0]  # 2-bit primary (lanes 6,7,8,10)
        lanes[0].extend([0, 0])
        lanes[1].extend([0, 0])
        lanes[15].extend(list(s_m4))
        for c, (ln, bits) in enumerate(((2, 5), (3, 6), (4, 5), (5, 5))):
            lanes[ln].extend([
                _zig(self._signed_mod_delta(ep2[0][c], 0, bits)),
                _zig(self._signed_mod_delta(ep2[1][c], 0, bits)),
            ])
        lanes[9].extend([0, 0])
        for y, ln2 in enumerate((6, 7, 8, 10)):
            ds1 = [_zig(self._signed_mod_delta(ix2_s1[y * 4 + x], 0, 3)) for x in range(4)]
            lanes[11 + y].extend([_pack_ix_pair(ds1[0], ds1[1], y), _pack_ix_pair(ds1[2], ds1[3], y)])
            ds2 = [_zig(self._signed_mod_delta(ix2_s2[y * 4 + x], 0, 2)) for x in range(4)]
            lanes[ln2].extend([_pack_ix_pair(ds2[0], ds2[1], y), _pack_ix_pair(ds2[2], ds2[3], y)])
        acc = (1 << 4) | (2 << 5) | (1 << 7)
        pos = 8
        for c in range(3):
            tc = 3 if c == 1 else c
            for e in range(2):
                acc |= (ep2[e][tc] & 0x1F) << pos
                pos += 5
        for e in range(2):
            acc |= (ep2[e][1] & 0x3F) << pos
            pos += 6
        for p in range(16):
            nb = 1 if p == 0 else 2
            acc |= (ix2_s2[p] & ((1 << nb) - 1)) << pos
            pos += nb
        for p in range(16):
            nb = 2 if p == 0 else 3
            acc |= (ix2_s1[p] & ((1 << nb) - 1)) << pos
            pos += nb
        self.assertEqual(pos, 128)
        expected += acc.to_bytes(16, "little")

        # --- Block 3: mode 0 all-zero block ---
        lanes[0].extend([0, 0])
        lanes[1].extend([0, 0])
        lanes[15].extend(list(s_m0))
        for ln in range(2, 15):
            lanes[ln].extend([0, 0])
        expected += b"\x00" * 16

        raw = encode_lanes(lanes, 7)
        out, prov = bcpack.decode_with_info(raw, 7, len(expected))
        self.assertEqual(out, bytes(expected))
        self.assertEqual(prov, set())

        # Inferred BC7 signature: strict refuses, provisional accepts and tags it.
        inf_rank = min(bptc.BC7_CONFIG_INFERRED)
        inf_a, inf_b = divmod(table["rank_of"].index(inf_rank), 16)
        lanes_inf = [[0, 0] for _ in range(16)]
        lanes_inf[15] = [inf_a, inf_b]
        raw_inf = encode_lanes(lanes_inf, 7)
        with self.assertRaises(bcpack.BcpackProvisionalError):
            bcpack.decode(raw_inf, 7, 16)
        out_inf, prov_inf = bcpack.decode_with_info(raw_inf, 7, 16, allow_provisional=True)
        self.assertEqual(len(out_inf), 16)
        self.assertIn(f"BC7 signature {inf_rank}", prov_inf)

        # Built-in BC7 history ref without external history: strict refuses with --history hint.
        def _bc7_hist_chunk(k, nblk=1):
            de = 256 - k
            diff = de if de < 128 else de - 256
            l0a, l0b = _deint4(_zig(diff))
            ls = [[0] * (2 * nblk) for _ in range(16)]
            ls[0][0:2] = [l0a, l0b]
            d1a, d1b = _deint4(1)
            for bi in range(1, nblk):
                ls[1][2 * bi:2 * bi + 2] = [d1a, d1b]
            for bi in range(nblk):
                ls[15][2 * bi:2 * bi + 2] = list(s_m6)
            return encode_lanes(ls, 7)

        k_conf, k_prov, k_lr = 11, 19, 27
        raw_h1 = _bc7_hist_chunk(k_conf, nblk=1)
        raw_h3 = _bc7_hist_chunk(k_conf, nblk=3)
        with self.assertRaisesRegex(bcpack.BcpackProvisionalError, "--history"):
            bcpack.decode(raw_h1, 7, 16)
        with self.assertRaisesRegex(bcpack.BcpackProvisionalError, "--history"):
            bcpack.decode(raw_h3, 7, 48, allow_provisional=True)

        # External runtime BC7 history: confirmed, provisional, and partial+last-resort.
        ep_entry = [0x65, 0x3A << 1, 0x51 << 1, 0x70 << 1, 0x92, 0x1F << 1, 0x24 << 1, 0x61 << 1] * 3
        bc7_doc = {
            "historyEndpoints": {str(k_conf): ep_entry, str(k_prov): ep_entry, str(k_lr): ep_entry},
            "historyEndpointBits": {
                str(k_conf): [8] * 24,
                str(k_prov): [8] * 24,
                str(k_lr): [6] * 24,
            },
            "historyEndpointConfirmedBits": {
                str(k_conf): [8] * 24,
                str(k_prov): [0] * 24,
                str(k_lr): [0] * 24,
            },
            "historyEndpointLastResort": [[k_lr, 0, 0, 0]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            hist_dir = os.path.join(tmp, "hist_dir")
            os.mkdir(hist_dir)
            with open(os.path.join(hist_dir, "bc7.json"), "w", encoding="utf-8") as fh:
                json.dump(bc7_doc, fh)

            # Confirmed entry: strict accepts and matches exact mode-6 block bytes.
            out_c, prov_c = bcpack.decode_with_info(raw_h1, 7, 16, history=hist_dir)
            self.assertEqual(prov_c, set())
            # Zero-delta mode-6 block from ep_entry and zero indices.
            exp_h = 1 << 6
            pos = 7
            for c in range(4):
                for e in range(2):
                    v = ep_entry[e * 4 + c] >> 1
                    exp_h |= (v & 0x7F) << pos
                    pos += 7
            exp_h |= (ep_entry[0] & 1) << pos
            exp_h |= (ep_entry[4] & 1) << (pos + 1)
            self.assertEqual(out_c, exp_h.to_bytes(16, "little"))

            # Unconfirmed entry: strict refuses, provisional accepts via in-memory dict too.
            raw_prov = _bc7_hist_chunk(k_prov, nblk=1)
            with self.assertRaises(bcpack.BcpackProvisionalError):
                bcpack.decode(raw_prov, 7, 16, history=bc7_doc)
            out_pr, prov_pr = bcpack.decode_with_info(
                raw_prov, 7, 16, allow_provisional=True, history=bc7_doc
            )
            self.assertEqual(out_pr, out_c)
            self.assertIn(f"BC7 endpoint history {k_prov}", prov_pr)

            # Partial-depth (top 6 bits) + last-resort entry: strict refuses, provisional labels both.
            raw_lr = _bc7_hist_chunk(k_lr, nblk=1)
            with self.assertRaises(bcpack.BcpackProvisionalError):
                bcpack.decode(raw_lr, 7, 16, history=hist_dir)
            out_lr, prov_lr = bcpack.decode_with_info(
                raw_lr, 7, 16, allow_provisional=True, history=hist_dir
            )
            self.assertEqual(len(out_lr), 16)
            self.assertIn(f"BC7 endpoint history {k_lr} (top 6 bits known)", prov_lr)
            self.assertIn(f"BC7 endpoint history {k_lr} (last-resort)", prov_lr)

        # Mode-1 shared p-bit mismatch in strict mode raises BcpackError.
        lanes_pbit = [[0, 0] for _ in range(16)]
        lanes_pbit[15] = list(s_m1)
        lanes_pbit[2] = [_zig(1), _zig(0)]  # R0 LSB=1, R1 LSB=0 => shared p-bit conflict
        raw_pbit = encode_lanes(lanes_pbit, 7)
        with self.assertRaises(bcpack.BcpackError):
            bcpack.decode(raw_pbit, 7, 16)


def encode_bc7_mode6_blocks(blocks, *, first_ep_history=None):
    """Encode raw BC7 mode-6 blocks (16 bytes each) into a codec-7 BCPack chunk.

    When `first_ep_history` is `(entry_index, ep_row_24)`, block 0 predicts its
    endpoints from built-in history `entry_index` instead of zero.
    """
    table = bptc.load_bc7()
    rank = table["config"].index((6, 0, 0, 0))
    s15a, s15b = divmod(table["rank_of"].index(rank), 16)
    n = len(blocks) // 16
    lanes = [[] for _ in range(16)]
    for i in range(n):
        acc = int.from_bytes(blocks[i * 16:i * 16 + 16], "little")
        assert (acc & 0x7F) == (1 << 6), "expected mode-6 BC7 block"
        pos = 7
        ch = [[0, 0] for _ in range(4)]
        for c in range(4):
            for e in range(2):
                ch[c][e] = (acc >> pos) & 0x7F
                pos += 7
        p0 = (acc >> pos) & 1
        p1 = (acc >> (pos + 1)) & 1
        pos += 2
        ch[0][0] = (ch[0][0] << 1) | p0
        ch[0][1] = (ch[0][1] << 1) | p1
        ixs = []
        for p in range(16):
            nb = 3 if p == 0 else 4
            ixs.append((acc >> pos) & ((1 << nb) - 1))
            pos += nb
        if i == 0 and first_ep_history is not None:
            k, rep = first_ep_history
            de = 256 - k
            diff = de if de < 128 else de - 256
            l0a, l0b = _deint4(_zig(diff))
            lanes[0].extend([l0a, l0b])
        else:
            rep = (0,) * 24
            lanes[0].extend([0, 0])
        lanes[1].extend([0, 0])
        lanes[15].extend([s15a, s15b])
        for c, ln in enumerate((2, 3, 4, 5)):
            mod = 256 if c == 0 else 128
            sh = 0 if c == 0 else 1
            for e in range(2):
                d = (ch[c][e] - (rep[e * 4 + c] >> sh)) % mod
                if d >= mod // 2:
                    d -= mod
                lanes[ln].append(_zig(d))
        for ln in (6, 7, 8, 9, 10):
            lanes[ln].extend([0, 0])
        for y in range(4):
            ds = []
            for x in range(4):
                d = ixs[y * 4 + x]
                if d >= 8:
                    d -= 16
                ds.append(_zig(d))
            lanes[11 + y].extend([_pack_ix_pair(ds[0], ds[1], y), _pack_ix_pair(ds[2], ds[3], y)])
    return encode_lanes(lanes, 7)


if __name__ == "__main__":
    unittest.main()
````

## history_snapshot.py

SHA-256 `ea31fb9620ad2fd0b4e70489952c2c68bfab7e4b6032819495a226a22a1c9c0e`

````python
"""Fixed BPTC (BC6H and BC7) codec constant tables for `tools/bcpack.py`.

All values here are codec-level constants (D3D11/Khronos BPTC partition and
anchor tables, BC7 signature rank table, and BCPack's built-in initial history
tables for BC6H and BC7), not game texture assets. Lazy-loaded so BC1/BC3/BC4/BC5
decodes pay no startup cost.

Provenance:
- Partition/anchor tables: standard D3D11/Khronos BPTC specification.
- BC7 signature table (286 entries; 10 inferred-only ranks marked in
  `BC7_CONFIG_INFERRED`) and BC6H/BC7 built-in history tables: recovered
  clean-room with confirmed, provisional, and last-resort entries kept strictly
  separate so default strict decoding refuses every unconfirmed entry.
"""
import base64
import struct
import zlib

# Standard D3D11/Khronos BPTC 2-subset (64 x 16 pixels, 1 bit/pixel) and
# 3-subset (64 x 16 pixels, 2 bits/pixel) partition masks.
_BC7_PART2_PACKED = (
    0xcccc, 0x8888, 0xeeee, 0xecc8, 0xc880, 0xfeec, 0xfec8, 0xec80,
    0xc800, 0xffec, 0xfe80, 0xe800, 0xffe8, 0xff00, 0xfff0, 0xf000,
    0xf710, 0x008e, 0x7100, 0x08ce, 0x008c, 0x7310, 0x3100, 0x8cce,
    0x088c, 0x3110, 0x6666, 0x366c, 0x17e8, 0x0ff0, 0x718e, 0x399c,
    0xaaaa, 0xf0f0, 0x5a5a, 0x33cc, 0x3c3c, 0x55aa, 0x9696, 0xa55a,
    0x73ce, 0x13c8, 0x324c, 0x3bdc, 0x6996, 0xc33c, 0x9966, 0x0660,
    0x0272, 0x04e4, 0x4e40, 0x2720, 0xc936, 0x936c, 0x39c6, 0x639c,
    0x9336, 0x9cc6, 0x817e, 0xe718, 0xccf0, 0x0fcc, 0x7744, 0xee22,
)

_BC7_PART3_PACKED = (
    0xaa685050, 0x6a5a5040, 0x5a5a4200, 0x5450a0a8, 0xa5a50000, 0xa0a05050,
    0x5555a0a0, 0x5a5a5050, 0xaa550000, 0xaa555500, 0xaaaa5500, 0x90909090,
    0x94949494, 0xa4a4a4a4, 0xa9a59450, 0x2a0a4250, 0xa5945040, 0x0a425054,
    0xa5a5a500, 0x55a0a0a0, 0xa8a85454, 0x6a6a4040, 0xa4a45000, 0x1a1a0500,
    0x0050a4a4, 0xaaa59090, 0x14696914, 0x69691400, 0xa08585a0, 0xaa821414,
    0x50a4a450, 0x6a5a0200, 0xa9a58000, 0x5090a0a8, 0xa8a09050, 0x24242424,
    0x00aa5500, 0x24924924, 0x24499224, 0x50a50a50, 0x500aa550, 0xaaaa4444,
    0x66660000, 0xa5a0a5a0, 0x50a050a0, 0x69286928, 0x44aaaa44, 0x66666600,
    0xaa444444, 0x54a854a8, 0x95809580, 0x96969600, 0xa85454a8, 0x80959580,
    0xaa141414, 0x96960000, 0xaaaa1414, 0xa05050a0, 0xa0a5a5a0, 0x96000000,
    0x40804080, 0xa9a8a9a8, 0xaaaaaa44, 0x2a4a5254,
)

# Second and third subset anchor pixel indices (subset 0 anchor is always 0).
# BC6H two-region partitions use the first 32 entries of BC7_ANCHOR2.
BC7_ANCHOR2 = (
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
    15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6,
    6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15,
)

BC7_ANCHOR3A = (
    3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3,
    3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
    8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15,
    3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3,
)

BC7_ANCHOR3B = (
    15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8,
    15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
    15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8,
    15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8,
)

# BC7 signature rank -> (mode, partition, rotation, index_selection).
# Lane 15 element pairs (a, b) map to ranks ordered by ((a + 1) * (b + 1), a).
BC7_CONFIG = (
    (7, 63, 0, 0), (7, 62, 0, 0), (7, 61, 0, 0), (7, 60, 0, 0), (7, 59, 0, 0), (7, 58, 0, 0),
    (7, 57, 0, 0), (7, 56, 0, 0), (7, 55, 0, 0), (7, 54, 0, 0), (7, 53, 0, 0), (7, 52, 0, 0),
    (7, 51, 0, 0), (7, 50, 0, 0), (7, 49, 0, 0), (7, 48, 0, 0), (7, 47, 0, 0), (7, 46, 0, 0),
    (7, 45, 0, 0), (7, 44, 0, 0), (7, 43, 0, 0), (7, 42, 0, 0), (7, 41, 0, 0), (7, 40, 0, 0),
    (7, 39, 0, 0), (7, 38, 0, 0), (7, 37, 0, 0), (7, 36, 0, 0), (7, 35, 0, 0), (7, 34, 0, 0),
    (7, 33, 0, 0), (7, 32, 0, 0), (7, 31, 0, 0), (7, 30, 0, 0), (7, 29, 0, 0), (7, 28, 0, 0),
    (7, 27, 0, 0), (7, 26, 0, 0), (7, 25, 0, 0), (7, 24, 0, 0), (7, 23, 0, 0), (7, 22, 0, 0),
    (7, 21, 0, 0), (7, 20, 0, 0), (7, 19, 0, 0), (7, 18, 0, 0), (7, 17, 0, 0), (7, 16, 0, 0),
    (7, 15, 0, 0), (7, 14, 0, 0), (7, 13, 0, 0), (7, 12, 0, 0), (7, 11, 0, 0), (7, 10, 0, 0),
    (7, 9, 0, 0), (7, 8, 0, 0), (7, 7, 0, 0), (7, 6, 0, 0), (7, 5, 0, 0), (7, 4, 0, 0),
    (7, 3, 0, 0), (7, 2, 0, 0), (7, 1, 0, 0), (7, 0, 0, 0), (6, 0, 0, 0), (5, 0, 3, 0),
    (5, 0, 2, 0), (5, 0, 1, 0), (5, 0, 0, 0), (4, 0, 3, 1), (4, 0, 3, 0), (4, 0, 2, 1),
    (4, 0, 2, 0), (4, 0, 1, 1), (4, 0, 1, 0), (4, 0, 0, 1), (4, 0, 0, 0), (3, 63, 0, 0),
    (3, 62, 0, 0), (3, 61, 0, 0), (3, 60, 0, 0), (3, 59, 0, 0), (3, 58, 0, 0), (3, 57, 0, 0),
    (3, 56, 0, 0), (3, 55, 0, 0), (3, 54, 0, 0), (3, 53, 0, 0), (3, 52, 0, 0), (3, 51, 0, 0),
    (3, 50, 0, 0), (3, 49, 0, 0), (3, 48, 0, 0), (3, 47, 0, 0), (3, 46, 0, 0), (3, 45, 0, 0),
    (3, 44, 0, 0), (3, 43, 0, 0), (3, 42, 0, 0), (3, 41, 0, 0), (3, 40, 0, 0), (3, 39, 0, 0),
    (3, 38, 0, 0), (3, 37, 0, 0), (3, 36, 0, 0), (3, 35, 0, 0), (3, 34, 0, 0), (3, 33, 0, 0),
    (3, 32, 0, 0), (3, 31, 0, 0), (3, 30, 0, 0), (3, 29, 0, 0), (3, 28, 0, 0), (3, 27, 0, 0),
    (3, 26, 0, 0), (3, 25, 0, 0), (3, 24, 0, 0), (3, 23, 0, 0), (3, 22, 0, 0), (3, 21, 0, 0),
    (3, 20, 0, 0), (3, 19, 0, 0), (3, 18, 0, 0), (3, 17, 0, 0), (3, 16, 0, 0), (3, 15, 0, 0),
    (3, 14, 0, 0), (3, 13, 0, 0), (3, 12, 0, 0), (3, 11, 0, 0), (3, 10, 0, 0), (3, 9, 0, 0),
    (3, 8, 0, 0), (3, 7, 0, 0), (3, 6, 0, 0), (3, 5, 0, 0), (3, 4, 0, 0), (3, 3, 0, 0),
    (3, 2, 0, 0), (3, 1, 0, 0), (3, 0, 0, 0), (2, 63, 0, 0), (2, 59, 0, 0), (2, 58, 0, 0),
    (2, 57, 0, 0), (2, 54, 0, 0), (2, 53, 0, 0), (2, 52, 0, 0), (2, 47, 0, 0), (2, 43, 0, 0),
    (2, 42, 0, 0), (2, 40, 0, 0), (2, 38, 0, 0), (2, 37, 0, 0), (2, 35, 0, 0), (2, 34, 0, 0),
    (2, 32, 0, 0), (2, 23, 0, 0), (2, 21, 0, 0), (2, 18, 0, 0), (2, 17, 0, 0), (2, 16, 0, 0),
    (2, 11, 0, 0), (1, 63, 0, 0), (1, 62, 0, 0), (1, 61, 0, 0), (1, 60, 0, 0), (1, 59, 0, 0),
    (1, 58, 0, 0), (1, 57, 0, 0), (1, 56, 0, 0), (1, 55, 0, 0), (1, 54, 0, 0), (1, 53, 0, 0),
    (1, 52, 0, 0), (1, 51, 0, 0), (1, 50, 0, 0), (1, 49, 0, 0), (1, 48, 0, 0), (1, 47, 0, 0),
    (1, 46, 0, 0), (1, 45, 0, 0), (1, 44, 0, 0), (1, 43, 0, 0), (1, 42, 0, 0), (1, 41, 0, 0),
    (1, 40, 0, 0), (1, 39, 0, 0), (1, 38, 0, 0), (1, 37, 0, 0), (1, 36, 0, 0), (1, 35, 0, 0),
    (1, 34, 0, 0), (1, 33, 0, 0), (1, 32, 0, 0), (1, 31, 0, 0), (1, 30, 0, 0), (1, 29, 0, 0),
    (1, 28, 0, 0), (1, 27, 0, 0), (1, 26, 0, 0), (1, 25, 0, 0), (1, 24, 0, 0), (1, 23, 0, 0),
    (1, 22, 0, 0), (1, 21, 0, 0), (1, 20, 0, 0), (1, 19, 0, 0), (1, 18, 0, 0), (1, 17, 0, 0),
    (1, 16, 0, 0), (1, 15, 0, 0), (1, 14, 0, 0), (1, 13, 0, 0), (1, 12, 0, 0), (1, 11, 0, 0),
    (1, 10, 0, 0), (1, 9, 0, 0), (1, 8, 0, 0), (1, 7, 0, 0), (1, 6, 0, 0), (1, 5, 0, 0),
    (1, 4, 0, 0), (1, 3, 0, 0), (1, 2, 0, 0), (1, 1, 0, 0), (1, 0, 0, 0), (0, 15, 0, 0),
    (0, 14, 0, 0), (0, 13, 0, 0), (0, 12, 0, 0), (0, 11, 0, 0), (0, 10, 0, 0), (0, 9, 0, 0),
    (0, 8, 0, 0), (0, 5, 0, 0), (0, 4, 0, 0), (0, 3, 0, 0), (0, 2, 0, 0), (0, 1, 0, 0),
    (0, 0, 0, 0), (2, 62, 0, 0), (2, 61, 0, 0), (2, 60, 0, 0), (2, 56, 0, 0), (2, 55, 0, 0),
    (2, 51, 0, 0), (2, 50, 0, 0), (2, 49, 0, 0), (2, 48, 0, 0), (2, 46, 0, 0), (2, 45, 0, 0),
    (2, 44, 0, 0), (2, 41, 0, 0), (2, 39, 0, 0), (2, 36, 0, 0), (2, 33, 0, 0), (2, 31, 0, 0),
    (2, 30, 0, 0), (2, 29, 0, 0), (2, 28, 0, 0), (2, 27, 0, 0), (2, 26, 0, 0), (2, 25, 0, 0),
    (2, 24, 0, 0), (2, 22, 0, 0), (2, 20, 0, 0), (2, 19, 0, 0), (2, 15, 0, 0), (2, 14, 0, 0),
    (2, 13, 0, 0), (2, 12, 0, 0), (2, 10, 0, 0), (2, 9, 0, 0), (2, 8, 0, 0), (2, 7, 0, 0),
    (2, 6, 0, 0), (2, 5, 0, 0), (2, 4, 0, 0), (2, 3, 0, 0), (2, 2, 0, 0), (2, 1, 0, 0),
    (2, 0, 0, 0), (0, 7, 0, 0), (0, 6, 0, 0), (255, 255, 0, 0),
)

# Ranks placed by ordering only (refused in strict mode; allowed when provisional).
BC7_CONFIG_INFERRED = frozenset((149, 151, 152, 153, 246, 248, 251, 252, 253, 254))

# Compressed BC6H built-in history blob (10,752 bytes uncompressed):
#   [0:6144]      endpointHistory [256][3][4] uint16 LE (W:16, X:10, Y:6, Z:6 left-aligned)
#   [6144:10240]  indexHistory    [256][16]   uint8     (4-bit left-aligned indices)
#   [10240:10496] endpointClass   [256]       uint8     (0=unknown, 1=fitted, 2=last-resort)
#   [10496:10752] indexClass      [256]       uint8     (0=unknown, 1=fitted, 2=last-resort)
_BC6H_HISTORY_B85 = (
    "c-qxiYiu0Xbv|?N%<Sy!?Ci>VKe>8XmMxlGi4sLhe5~FSMVTv-qNo?SB4be!C6TgaCwe3v*>Rl22E@WCP^3Y%j*T=;4Tx}p)"
    "^LDmQ`@jx*f7%q2~ZT(+Cu6dX=(yZ6SOtTe&^hk>)Mup1VMqWG<$ew=H7cA-}%nDOA)CIWr+TdW#<l0%eeJliRIL$g!TJezr"
    "24!-9;&iI<q=Ov#H!3=@x1s>W{1#wG!=kj1n}Ts3A*fT6)`cQrkvE&+_KyMW$MEM(?h_FyjYaGO}%pxu2gBdnmJ8<hAB+i5v"
    "?^WbXJ1^WML;nsGW!7G)_%EG>#gvetZP_S@Q<ZqMjAHBqr+L^sg}O7GYXxsGVOQ=aF?x0?5VFnz~$N}C?Bj9hKTYnI(HE`{o"
    "8wV0}jR!!;{Z6ZqLE%tk6$2Vve-9@==MVgDh##@RskLJ+yo-s|-NQ8L6`IKrZ=sL2gs^+@*Wg<B$eo4)GntrdiD@E2kXhPBR"
    ")&g2iRCwN+ODo{FZrL~8HfG|uW4DRV(kXIjCPgdKmS!By9=8JED4V~eo8i~mj&phwttZNjX$`wm`(yepx{s)5NYAAEDYaW`m"
    "(~(JkTZ6)WQ|=-W}nO>--N#!DRb7c9E^)+pTK?z%3b<L!2w-t!}={$xL8uNX&I&0zKY#v6V*Ix)>-y<RK@cyR9Wj_$K-{Z)_"
    "SU;+6x6e1OChm7Vuq9g~1{CxrNH7ud6j2pCi|CAD{IZ(!9^o5_YwzxHyYlmQnP@w6&NP5<Qx>l5{uadh*&voC-ZT-3l4yjif"
    "KXVYR@Y<xZl-Y~Mkm7%ZUd-&%_V|1SZ@ODMPQC6$FAiv8zB@64guf~Tt9oXE_No|X9I{$|p|X;ohC=T0s)W6R`C>3I2$I4q9"
    "5ZPtBeLN(AzDvkU###Ka3<HrB>MyA#k4d49nhgKDEIrY6om=9d+{EgKF`)`YLyDa>XnOC$dybngu7A!8F{6mu`jg|bVb}WOZ"
    "dqfVjzbW^p*Onyig-2h8KM|kv<H#Gt<zheNY|8B`>NNAyz7jD%m3Lo3e0(aeE~^^EHMd|K_ci6_O^AG_Q<Fy<|3~h67Wv;mn"
    "f@}Khg3B>iP;X|S;YO-R6dl)`aXE86H!SLwT<c!oI_1nOK_FW;_VnwkjJ-k`#k#Qn2EzHkr}^Lk)WD-&WDv(1;6EmCHSY69_"
    "x77<j0=hC>uOcwR2i+M1I_s$MWOw^G5LKa=j6DQ`;|;&p1B$2*nw{BSo>ReCAyWU^#tbLRIs7=Y9s<EurY#+k)S*H+u|^y;*"
    "JawO=!FyzmvwUWL5bf_$!~%!Nodz@OLly&||6-})nwRh=!rQ$3pQU1H6^dZWDyz=N>6dx@1|y|)izpJvpZ_mu^EQqA|kKTT9"
    "#GcC9%t~au<sv?h*x)=B?pNN2Gn+j*%QybvqLamQ{-$*}Q`8x8viqf@b^+MKoZ3+9XqQd$jSQj{5UP4^w+*Z$PC)NV*Nvb;a"
    "1Ng(ED`TGJV_e)hB6gSO{o3f&v|h&9>ay|6>JR09)skzbejPY1&kM~PjqLuJ@!OG-WkZjsr+_>|e)V2eDU6G!zb?-sa!q_rT"
    "6gqks_wYFH(mR_$>WtJk@-_|^;%j)@0=dh>tI1<ETyx+e|i5g@YWnEHor)0f2Q+~#1Gf=McoL0*Y3?~;lZ|<n6HRVeINB;0h"
    "NZILp@kPg^pi>#gbH;{ZpF3c~X51C}w#TUPoO%xgPthqiFaB*nS~Jr?*>6SRRjn@6}i*2i~qHI$c)lX$|r%kJ*@?--hoH^`H"
    "~DO;U8-^gE+9&xk*#mYaH4I-#tYoPWo^3!Jyo_{ihHQ6rT;cQ@)woNjz>P$!^aH27mRlkva(S>(%7n%uP<^}d=?xk#@<KQXy"
    "$t2GBmD6F4}yr`qx>Q}MqJoGCO^x8nz>++Z#r>gB^;B%YOV_S`X-MJzoXQs$PM}e4^Mt5oW6?xZA$eVSP?_Oku&@kH-SPA$g"
    "zlUX<GHv75LioG1{WAD}4(dk{{+);ZiA*2WJgFG3<@=`;*RO2<2hig#nmqhIW~1KjpB71{T*Rr7$|HfUg}$W^mm*sFwm7Le)"
    "&bUuQ&iZDDBn%Azo=`tcx>T(h`}!t$R-c<mt~x$dTLPwTdB~t8)%q8V>?^%HW+bRBk%%T<bH)H%>q9LhzHt*Jy}?bd~KXS9|"
    "7Mqj{z?;Z_fwle|*mWZO;pDrJ7#Fda!3vm6`>Al@nRy>kOhr6S$wE+S-Du1#YgadK$Z@DOGa`d=V$wTZR_k?T%^DyQO6syP_"
    "`axuMrXpWM&~sITa!>e5!4`TWs8Kz-Rnh4W9KZ@8DHzW9ck4_+t@-Hr8pyuVj(K)iEDJ9Ry9RI2%s$=4NR@^bD!7#tkDBC?!"
    ")vQoE)&HWP}==+fg)5DA(4PKrg-Z$4{^18J1hvvPeX*2KhUkBbdQFMV|?@}r}M)2=q8aw%A;AA0XM}BNA#r^c?<G|IuG`)rW"
    "gSx$89QZ*WvUb9XqfgH)dK&W=Kt74_O8D(-uy+|v?GJ%pl&=G!^jlYZ|3!J+cdd99s6$;_QCE={iQ`p1Q$&73@3CFzJAs#nE"
    "bu^*GJO%)!=ci?31o{0-Y6l9Jj!nSFRYIpa^uAKr-na6v><z*M_omHdR~T%p>ACjnLBg{es$0<^~2xD&(8l)yngYVi+!@#cU"
    "mXG6VcdDAlKX$KUcbLntrq|WyT#P@o)YJX^(lRzpNbWKhT%aT<@btmmyy^P~j2MTwimae;iskbnRg+{a*2cr2_Wfg);QpNac"
    "f7h|676?jx*{qUpmK%L5*xfp?)L)*mPn<E4C9S(_lE;~8r;^VrD<RSe@1Lf@Lat^U{dvlkRay#>xby0PaA*hf)ji1ZwI_{QK"
    "e#H*glM{g<@eZ!TFS=66^YB$^q9%-Sg>wCaAGbr6xLSCTX?z3SZ@ZR;Bl79BYpQt&g`{j`q?QnlEIs^XBQmLT9OZ9Z4{|0g2"
    "P&$+XuIi!3GsqL<Yu~q39W*QU{xf6~?26<4m6RKa@cu@MPQC{%Y$}D{5j&#yhD~4hRF}ws3v<CMV6GFp)O}oMhhIm1L*5-J!"
    ")p!HdgwjKdaCLx6Zd0uw1hgois)=s`ndAm4ET8wO?{zg)#J_5rN6T7X1y+#tb3S;j{O4OO2IDXYn%s0zsu}FwQV_z`?G8LE{"
    "l0?G~bSM3Gn+B?uTMj{@SY;`84^=YlsT&AN)_?-KSFD2Vmg@-RS;z8K-(*LDs{CT~j~}@}z?$QEje-eFBlqc(bZ$5@Xm^=!W"
    "-E&kA`&3Fo!LW03H7;fHDo_nQY5@R-H(U&EiPsI!Cf8!NVFAi-lh%{bSc!@lrq7fXkt4l~9pig~a+f7)v0y!T3|rz@%apf=}"
    "#6P5n{`~`EaAIL*{7yWD+=Xl_tHw$S|rnd@lZlvoy+{ZN1V|!B;`~RH-CCzz2eNQQtQ9e>J_zRtptoPw?<vd>*mj-VlE0G6-"
    "C1exuKk!eG$cMpS634ID{}W_y6L9tC7|rK%iMpTtII<Oa2Y;M;OYu3OJbW2_=pw!k9zz{@=t0!ufXZ7(iQ`61mtZ~Ct$z{YB"
    "uyR9sZ}_aPK{iKTtQQ3pMyW|A;SAE{FmC6LES;VwdAY@I4ysM@rHVK#zwyQG(B3vs^G0|Tl;)o=vocAjwT+s34Ktv_p*NI3%"
    "0+3F`jQr>1vK!8=s5kgXf+?ot{r)sNXEhLo1O_z*Qk*>co*iWM=QM$>Xl=h-))N?Z;3D8>p(Q8vTb$Q+r3TF6#KAza)-NY3M"
    "z!s;E0JKueoCPrV>@^me?FeS8b*Q$3A8X`#<rL;0_Is5e<EACF;NL!Bq;H21&76R#@n`-(&F;_W)*{acJ;y4wF!;{J>p#^8-"
    "s9BW3fEBeFwZowUGIUwgJs^@bK@}Oad;i+TygO71eeXtXF25$^41+N14TdwGpoCjOJiavzTOPBP0kdqJbxfy-fxo^WBm(pK&"
    "LB`Duwbm@yZ>>wCZ<s;WiW0t&$44{J8|x2Ps5^Dw-5KDsHB@MN-0;lOM@43;?vc7#99*IK+<bK~1N-YJb9h=wyg;CgUz*njD"
    "_~E0KXH8N=s5HMt_F=P9{vu{cKhFv2Konp2h{OGJK_v~9<WiL8fap8GyJ8fIDA>oSEU1&@r^q6Kwj*l_5$LG{oC?*?o#gI54"
    "9Z9<)bJymXW+3>v<7)0AKW^(Wlhn{I?u&twUcnj(lvU-2OD`<r?5}O2ye9`|g8(Yj9qOL!Sm3==wS8<{G?5vVX28p=ZOBxxH"
    "_rpP5hB&emWz==o3<-xggv6G8t*@c9tlMqEy97MUB^g{;B+&TG&I=cxQmtPB0y%lJJ6yxUVCzF*Z%;Nt*4+qGM(P#05uzcT)"
    "68y0@JvTeWV(|f;#ed;OO{UyW)INcQ?FTgX0zK_0Q6J0q#@Ma_Iei(KDKZnxNXJik0@I!)H_s@bKVpKXmB<Jkh#c}Y&Vk%zB"
    "qrXAkot_lE3uj&zSvt2_`rcF@S+%g_+P<>zQEG46;`0dVGWM^*xnUXPIw~DAl17H1=Q=8$IW2LGhBu>b;r@XqOkDeiq;62(6"
    "Ob4mE)oAeaHAp%eG{lUs24}a#9lf*B<CLLAJlT*J~RRQaE?0k7}f<Y_oc)ibmTd6|L|sv5%1p3az8uJEi&KVkN4})uWgp~#`"
    "bQ7b&9Tc=cQj6>pYBa#BKMG<ZZ641ntoO=3m2IA9+x~{Iyg%7>Rv_p6#MvRG5&yCUx{V_!qKo9An_2MVsGMTaBb$8mzDa^`w"
    "!rA92`;eeiq5`2pE4+Oq;uQ@SS-J)-u_qF3}lwcxC{uTAb}cIV9d7qlS%N=4E|BURTv`8_P%`6BT-$=~x9{Em7&l#y(ShH^#"
    "@<|^5<6jefD&1I;9+*wbfzE@G{p`V*`cE|V3d3@X7SL#(x^z77A@;giPFv)o)Iu|qRp5w8_{f*eow(^r4x@O@GVu{@P#D{!a"
    "Dc5#=+x1A<NHH&f1OX^+Bb5q+6n-zXQmHTu+!Uz74;9|EJ=<28`^ohb1upo}#}clMS8O}L()cU1MF?qBzPJyelnO(v6<8@1_"
    "&!QsWme$Xf#*UWH-LhHi%kPOKvNV#gJj@o<>40ws2td~<N2^5?s|cSV#-Q7uH!oiTPtNl$OmiqzOwMqxb4MUH<?TZ{KOAjm$"
    "zgE@mStriI1irz`QVkTS6O`#$-o3sdy}Ar#we1UH~RSVQ7aLfs@dImvG=AXu$jX$+&i1?P}Xjz<*+v6(l^@PXzdB%W>^k5IE"
    "X)Efwb#u%H(NFo*{-jyr+v`?gMKWvN)wQZ6nBe&PGJ?|Lrchkq(i<ojO0;glG;>`Db!s(>wpWIM5y2cP=vSHjrw5P$@{=OqH"
    "mb|F<#+fLvIY#1V`9S){%TP{2gFS%@Tf;H3}SDs>HE%CA!bK>!slknx@0Jtue2{^_;7|ai_V!(E>ae#{J`JT%LvK27U3W8+P"
    "!;TI=$Ez?0L!iU+75g7?i$m%l8F#d=U^Yzm;UN46{A^L%L$EQ^WCel=5iq>*68i(@2R<Zm)IIpnWd+1TD$s~M^!GH@Q=0b=L"
    "Z6)peSinRA;AI|B|8pG#1cv6CXyBgm55;*Pl+Be{K{{KNjqkRF|vKemFvc039OI|!_ZAiUa*URLm%-Aym;KUlL;sTdx@8V%C"
    "|le2aMqon-wArTm#sWHvI7!=<r7jpmF4$Joo)rjFlri<`CL`!V3jrHg4OD1>`^oxA<{5Cgyn#0uyk2pc><m)j*W-vd7+qa;y"
    "(2Ue;w_I1Euz>K1CDe*h}v$RNZ%)^l-G$J@X^?jfQGDeMgZ5(oa*Y#p@43m&Tl%XuJ+0doOEjyGo&IA1+>i}C};pQ}B#(Z^4"
    "l9A97D=`o*GxCXBv9b8bT3PEb5;$djvPuxuyOM(P+V*g_kW&~azZoxw~kD~*qFgG$4d5#<BZ9>wlsNw`rNl$bYf5Njd)&kFw"
    "`k0?!+=KtZz{kEmpn}{_s84=e4vK3S3)7*x9rut_oak=MQ|tyWs03d=4&H;J94Fi+fSVmI-f$&eu5!)5XFi3*i#F$q6BlZPS"
    "&WAO86VgmMGvGGdV&n56WGiHt_`e#%kUEw*l^YckrK*cx?sGp`)${xITU9y@l`y@EFoNtH5nDkOkkh$oj~xwH#n%`58xZf@s"
    "+1zJlT!=T&j2tW#|kf@5f_IFYFe^A6$rVd!ee348P016n}!#Jt+o=2pbXbIsmE79EG1I6w_ziW!)HF1akv%5}*KOg;9AZ`@x"
    "_1V%++!q`ibe+cCVDU^5(fz*L!#7;ru%1pIywW9U#a0mYE;pcgEIdgCfpxfuQ=;bC?Rpno9tcrhk*zyK734MVQi?26Fk{Pql"
    "2RU%1D_$Uy7x!@Z6Ljh2L)ICqAoa4#CV~-=gE@ulm1(CL8hYrJlRT6vIOW<bD78+-N3w*fl2p_1V>&hlr80sNb9F1Fb-xXKd"
    "!u7&;jCfvOY7{UDy#aVTk%)UJ&k5coiM2g;D_~ACn=uD{Jmx<?sp1I-^-CvxM>Ai-HImVs7EE1Sa5$clf3RKosQc^%PL4o&4"
    "UbEpVM8ufSebK#O|9TjnFTl=sGoRX_zCe0Q5Koh@ECN)`wLTgOc%g0Ht{M6$q6I+!*-@m=5-Qyd0Yaqa)MLUV}4;UCp^I`<B"
    "Ax&A!7pRh|Wl=JzvE1&U1aK@$kM)G2BC_k`<a@XS0butLB=7Fzm+rbLr&_3(%tkO8P%vsE&IC(FDkddy=TwpXUp_SWmVQ9RL"
    "hWDU=t>lltcv=L;dI3T$i{b1Mkki*GB>*`Ejkuf<uZxDn-sfUzn7;{fnod?6Rng7bZcv(o2)fgY0<S}f!n*Wr-yubp@x1m;R"
    ">>j~M(jF{Pv$&Q2SnWAa<p`xFuw-OwW^MP4h>;YIc=a;Dm94MG->cy?g@ENb;p*(Q&Cw#<hF=A_*P>WqYgMj^u=f+O47x5rI"
    "bX%M+=)u9(1pMG1M>}9HV6KrKhl?mS(?Zs^R50$sY}@P)nPfi1+T2U9?ZQ6++U{Fd5{1w=JmUx6t@yC782H@MDMljifY6F`D"
    "<8XZxeNkiyDL4Q5<c{}cV~ZMdm!LeckD5INs<C{P|~FT0xz)Y%vC`Ug3A=w8eW7AGWd5Hz!Gu8$5Oxy!;yps@WomZFIDj+;}"
    "(KsW9}^~{2xd@%L1k!x`i`b+*bva<cf>i?F!zdSCRRiG=9GDr7isGiqlMY2LBuOGz`k>a`|PGJmv`7z*)G2{ULm<02UsJzKl"
    "vfasW=;U&59UPUFtjPV(`<_CkTEt(=hKt%QuEHDmuem3~Efe$GFxla=1bV;<((Y;3@{%O|`FAsHJOJxrETy#u44gv<QrV<A&"
    "l$QYBN!~1cB827$OC}Cb-VrqZ#e8}XbK7Miik_|Ktc8)Uf=d+9G6OzZB8qS^-j1Y^DT}&2SV{kxl`Qmt*seFF4Szq>RDwLc6"
    "++5>a4krA=Sr&f$`i%2zC}in5u`sasc$>l%esqDA<$S_@Rmklc;u%BlRKY)gSpQqn4)LpKz_kKghR|Y0`0<PFyLGXB#4MIba"
    "x<vhl=tcLd-&;pvfnNFSs(tvz~WO8KISh{azrBQ(;vP^>VFTdkEU858-B)Q_0cxgXMf1D?)dzUlYWP}^jmNC|MEkh^(Tk!zX"
    "6|rKI8"
)

# Compressed BC7 built-in history blob (43,776 bytes uncompressed):
#   [0:6144]      historyEndpoints             [256][24] uint8
#   [6144:12288]  historyEndpointBits          [256][24] uint8 (known leading bits, 0..8)
#   [12288:18432] historyEndpointConfirmedBits [256][24] uint8 (confirmed leading bits, 0..8)
#   [18432:26624] historyIndices               [256][32] uint8
#   [26624:34816] historyIndexBits             [256][32] uint8 (known leading bits, 0..4)
#   [34816:43008] historyIndexConfirmedBits    [256][32] uint8 (confirmed leading bits, 0..4)
#   [43008:43776] historyEndpointLastResort    [768]     bitmask (bit k*24+j)
_BC7_HISTORY_B85 = (
    "c-rk;U5FglmA-YWs;BAt8}0f*EP5D%2x2j&<JE>Ch%hn23_^&GnRNy;gvMyi5JaeW$LjL9QmW}RvlXF)c`#vO%p#Vsh+u*qm"
    "XJUm#Io#)Wm)u)2S4n?z?wk>6MBVNnngRa-?_KCySnSNT4PI=WOr+7ZcqK(pL4$Ro$uTpjS&1RNmdS$c<C^_)D-cx^Mmv4_>"
    "xHD#-L53b&+OhlMAAqrquRSyLw8bw{POU^==wJ-^G311Z}w95YhTP?n^Po1@wV7KL49EN^yQ!TuELMTgh^1K0n>Ai#IRV#d}"
    "v@5dZPPqL}u&5-(QLc&VPmix^{RbY01-2T8Odl5}-yKS_N0zmmAIj~4G6gY)UNiz4|T75{SkhWOxvjluaJC2RX>^3r~}pE~B"
    "TtlI0>!@>Et;;$dHFrQXb?`?(RR@khIs7dzxu4pH1JhKKHrbGKD-@~<+VRwvQSQqZwN#o=1(*0<0oqV%^dtbvdujAZmFO8cx"
    "w~C`Fw!$;lqxf_;y|yBDV<C3ZC9$+be))z-)0bpQc1wr-d%ie0IQaE}`LlWP&)My%c1z<3em~i5qivxb&i|5Lo5IgpPvHl1f"
    "?a@*H5~OlYO^$-f4uW?8VmHbgZIP!w_?~UZuH8y#n_3c?xf=O?HzG*IPSK_Xxu?RLp;Nl`|YH&pT=j^wP<}wWKF{HDxOJkZd"
    "GAa+l|iu6l453&RxTtPffK$o8|-ep)1iT%s-8GKf?O<+VSpQ9G~3F)>p;u&T+)hQt$G{%Ka!jjpr^E?D=P8Q?UWxUP~eo!8T"
    "C}+a)jD113JX+Ie0?8|wu-yofk@>3>RoL2M<-QW@u|wp}|D;&O4GNqhfqlau>#v>`U*VZ3DUUlgAZeZ2KwZ^!54cIRcr4zFu"
    "00(%i*u?Z}aol}a>Qy70y#YUE%!n*31dk7!T58B~;$evY6SU?Lq>UQJJb0Xe23mcq=ozE6<5+0=K{6QLrxNlzjHl==!!|%V}"
    "Z&R$qzZYo;?1y(?gKrW)^pf~YZ!;R=s~ueehgsdtbWOws-XPqh>G@Cc7V}v`3m(H-wh*6fv@zN+i^Oh9@qh7d5-;Gm2&^x3*"
    "H?E%lr4x>5*}>C^9NBB_BNvVUX+FcR4I~Z6){xru7QWw*N+#*ts^GZaMbTo91YJu*VUZ+Tz8XN*fUkUN;dt5`0cNo;$Lq?1;"
    "1=6K0%!7xnrIb_bKK_V`Q-_h&KlPr@w-Yeunk~*y!E6X?g=#+`+m|-b>=>UK|6LG2s(_q}Yz1$GxY^{6I03{-rFR*D=%9aSU"
    "Es5Mc-|fUVLv!$F*o74ARt9Ohe1<1-_Cl|<@!tK9$Bao@`_1>dT5uAc(tmWUJga1OC}ajz4f-ph8@MHcpOug+6HOxxm0dO`g"
    "hMdZgS=F-7Y#d~l{<EFTde#pjGFh+X=@!MG}jQfh_zPPccxR2J<B>PyWw&Und5?gy|7~#OZVTe91cHuK%<f4j;L0&`rZec!h"
    "=e$@6PY(T<{t{!nFUTKh{61pnCf1ZG&P&r3No^;6wSXURZt7}&L%Y7z6ph9mV7q}>SviQqm0r5BI>6Od^5*_l^4v$4qX^Gb3"
    "wU@DeZPP?z9^D67lwHac#eSQA0X}`6<eVQDX!zM-rGum6X3EFZzwGg!Uu`=c^MDsd3h~azAt12KQ+(?xTo2L9iGRWC?^A7$j"
    "!uulsnUua*0drU1}GW!K)#7A~{7kl*BbfJieW-9Bjp}9&B7ZgLw|~!d3!4N{HWxm(WIw7z12^aofo?h3htQK>xK7hlttv-sM"
    "QQ&E`#!?d;*%Gu<{~LGuZ5+r099lC1tOaCKPHEy=f7{e$@216KC3_&6{!zc=Ki^==eB*WK=10?!=B8i3`nuKMVtEBDiAP3&a"
    "upr3c(+bhr;8{o-!_k3a83wY+$K|AD!6nf?>`=miA_Od8cHco-JB>B6%egCHBfnC@~_W=ye$H=o;xTv&9J6^;5mw<in=cRSb"
    "lg?8vLfj_j$vz`_xlQqa+!(_CSL2O>jylneFNNJ0Z4`%l!}B`N0-lIxA*zi9(YW1J*k~h$`t1(5Hrt_`)1eq1v{ASts-muV="
    "be<s7h*H57VPjVs{`I^Cm-OMcQJRw8F+6CIsvhv;z{Kgr4z_T4W&Di&dR7xQ~AphI)7PWzPBKLv)rRRhq#+R*hC-gm@u*|h`"
    "X;qGj46Jh*wvi7r%Ias2e?3>oFIuJ-Gjmg}7b-CP=p|DBUvThqSNJyRphq_?fU0twY<Mf&N(+n-OAQ2{>QuVVydMAeT^15sh"
    "wBEO(KQBjkl>p}Up5fmr^E7}a$ba$Q&OBkrR$w8N%I)=%9Y;udid9siJQM)5_tA`FicPI6!AHUmb8Z(&bx_VOQ;U88f_zE}r"
    "gnK1p6>~-;z?6m@K)TN5mlzjTaFs{?uetY8=Sg(Z~u_Kz$+F1klL}x$Al0UhZVLqGSlJy4q$DG^g39)gpBi2^B;`?a(uOEUp"
    "+MBBfn`r|Yb`>$-(7sQWpes-V5Z0sBJ&MH)c5bITpQO?Jy{p8@>2akcGvu~*azpWUJJ!6Nh8kCCa#pRG)03O2#(R<$^f2=Km"
    "4tj=$2GK3U2&qWr_L!1k}etI@FM!!5a~u!Y=?1`)=C@=A9j^5Ve?K@92dNaI3zC9IA6$dej2!~-zQF`v56xil?Pu^8Z-u`ex"
    "`ICaD@Z&|70i4?o-|*y*<S3N&LL4v|yX;u+s$3H%G9bTH;XX8Q59pakVb!K5$G%z9!7XEBXB^1--2>1RU<HCTZit!THS##`g"
    "AWhrjGL#CfYRrt6S5bz898ck?{H)>Bwl@lG-Fa?WAPsvXv$D+lkSuO1jBK3}K0SJlU8=hv~;Fs$p`lAKhzg>uXQZ#i#Yjn0d"
    "uY*-hxqZ5e75V3j!&xD0|ht0Ql;lugvPPlw)XZ?=2o*h^HY+*jc;Z$SoA{RwzQ}aeVY=?Q_>q^s5{Y$y9|Jsb|A44-)+wgaY"
    "xl)cN&ANqHyOMlW%^jLh`zxY8H^Aqo!2ihkO`Hog{uO7aI%`>Ld6mCX@z(dx-T&d6jf1it01qHG+L-(0%S#1(c0Ngy>OI62>"
    "{0Cw<Kmo(0TI0{{s}slv|fn*H{+FFgd+w<(84wiad*B)xeB_l(d(!-y*unbME@u5k&VgLLpz_t7>!()74VbPbG@Nj6_4N~af"
    "$F6HYC+3aeB6JzmFVy3A{mi`%<o%8sbOcD+e9e;hl{OBEI~}Fpq<Ou0XeJrj%c>2G}DC^La=q35OBYBg&pj;-%9|;>OKbM3-"
    "W5wR2wAvWSU)xMA%zSAVxh_V1(@RjrVsuH5ci?7ndkT%Vm$_YLijcu-pVEcO%5R7n>p9ZhT18cS)dVcae3k+yDA8<WOf(EAU"
    "VJFNjaL2MS{i||49WIO&?wetdbd8eUtm*R9)Pt+BzsHGabgFF|b->Yes^HQo}KUJ7rQP?fkxx}IUR_Vz|&GVxuYIZwRk0PGC"
    "-7a!oUE>lyk12<trF=xXn&SEj;^=MkACv8)hVnt0tV1uI+t+z>S#yKZIm>EKA<C9}H=q@cFD#1gZ`QTFv?krtZGUZxLSv`U5"
    "{58G*u1Ox8g&6m;}35tOn#Kc*Y{IZlV30HZ>$2(;B@d)=M@0FE<U_X+GHNN{aUx*hK&?)(bT?e4}7e~Aph#T?habQW^^4jM)"
    "F3!-iw(3^4>1677}kO{4eJCU##kW78P#c`yTS<9n7mrm{ogK$>O~<dHtSR8?BMni}?gYozuJDyV;wk1>-3A@I$n~VGs7tb#k"
    "=0r|a28<X+e&#9j{UlE5zgcInnlWjm@RRV@miCd&SZi{^sDr>YH_<X2#6X9?>iJG@IZ+n`lBYKQ9O<9nLp@|J1^<j22XyC9n"
    "HpBL}1UFg2{-uY@)Z-}PSB#XE=+S`iH;NDp21j@f#vA?&K{2R`@dt1@%ydJ!T`!m?t-EWhAh^o4_L%Rj-e1$Z0+~_7@{rCdx"
    "|6y|}k5k%1I*a{*)3;QN0zdiwnAqI-1Nfv@zzO=MF_e$9LVj5lZ%50jPNW!UqE^%Uir>Wj-`gjg5Z1Fu#|`C5%9&)dOts6nM"
    "q@8yy%+bk<K;VVh0vDd_pp&`^99-$QEf`O2=?FJ76&KX%1XK|dJFSn^%fxg;T_6HFXs8EuJTc&Vq#I%)mSHN*-&--4%O-Fi@"
    "5g;)_h7_$2_CXsl1LmrS>^VpXmCoF1mGq;TF|p-_(0#@tOKoynI~WzpV2n@-O0irxUGe+~U~Y-Vi6;n$_u0TOHYlR2YrLLOZ"
    "WbcCo*NIeyfR8z0eJ+can8_lCj<VPy^Ndu!)K17q$kPv7T$T(7ygN>v?|ilAd~zEY{=hdOWDwmNY0Tz=Se^v~lSyLgoD$GIw"
    "VetbSSH*!pS_4_H!zyBILKhX{qWdqI*{WXo8pEUnz_gAraI&8}lbX0Lt9k{nTet(r&*A%}f6Du?4=f~#LA9s>{bU*a(;p|`Z"
    "IgM3X@0i~w;RNsJ@?&&9xP^`~Zu9Q*<#KqaJ^&AcarH@UxZ-?tFZRRYr|-s+zw%z0^^W*)d|m21>_6^b4(BWm^9LBasTYg4I"
    "Tmjt$29y8ah}_=kGByV+QoIT@m|1>n&-pbKaTUhU#c`_8UF*nOpD)%ahKz>gsUlhs4!9Bfd`B`(ob<d)d%tI1MJzqcWj<KUz"
    "OuGk5jT|!H@ZUWqj(MCgP-@N2b_eB0g>H$VvSV=`f#v{xgkH;q5jluZ`o1olpOHCf<kV3UN`m|Do2KpRZO+^RKdgFX3=#=RV"
    "(#;A+aa55Sc*unlLQQNAtvtD;#rx4&&q?q?9c_8ep9Y4d;3`D!_zGI-AYW#{%U;?`#DoSUbNPyKIFKBX?^3VChL)<`}A4*Ta"
    ">|CVqvAwN!xi$eb+I2@0c;r+wB_7M6?pJU^++SgGdaXpr&isSb4a&_Ep)xLdf#y(?sPy<)z7@nV$AC<6X@mZa0=TbkoS&ut6"
    "s%IvSTP^tAD&liQ-xkIl;q8Haa=cB;v!(O)IBxZ8n%xRHY0w24@z8mVIj;zX(Y-dK6DHcTI$YO?uI`Vj;=Yi_^ZCyea;(0eY"
    "+1Dj`P8x%mpwp7RVS=#L}yOtz5L%`+|j&K8TS`yPGDcne>A_(<wt2;o;Ngrrs>H^_Gi{Lo=;hS_4B=QLS<xKllX_PJ0|L%QC"
    "yYoANOOSHkuo?{{(+kCg_||{^#n-A|ICQHVx;K=A*l<R5|`+{4$~gt-}3db?$gS5737^|4gX+`u7*}a)rr9eVmNfk8^zoA5s"
    "5s`roch*q6xTsKVIc0sXW1QMN4hQ;5@%{57V}r|R4M{z>~brFrIdtd@9k0<QA;P0};fhs+lb#B;T*Tly~N)@w8N8J&+kqGK!"
    "hx@<<@+ICqNRr!4nRxjE8mo=)Zb8K>Tu3bDP)}e#A7}L*V{7_~5Qh6{Ahxw(bpVb=dJm1-adayEquSz^w<^5RD+XejF56CYz"
    "&3~ePuBxBsig@7dFg-48wYqV?z}{7Ru6&+!fjw$ZTLWlJKlJ0svgfR!uCs@@J<>ivDUOKai*YehSF*adU(1f*ziJQoR;_tre"
    "lPJ}MdM)-zZJ%%{s;RfwpGe^m63hCF?~|r|786*z~^v2dZRqA&6s`K@i?M;D|2Pt#p;S@<uwUc)9!!T*EK1RJZif=u6Y)4JH"
    "i{&`uVK$?5C+o`^=x!&bdH4nw=|?_q|K|PI@=4@~HgsWq(b=PhV&swIAeot&^wV`B~waquOB_-e4I5@gwJ-aXxtrd^@r)`4r"
    "$*=QFaas64eiF!ZA|q$!^~o{vh<pDEv24F2;N_>}qOap(QXzjwiZF7_x#(8mOvA2BY5`zof=u}|vNm;a9zSF)&QSibAmp`W*"
    "&?C<}7-a7M1>D#0BKR918l}>nE<BsFv@yG9{)Bh876z#==KP`&gPZ7UQiYK2o9s8`zlXgfdOkN)3O<bxx0-ZzpeC`PPoW`BA"
    "AHCkF3cl`p{QBo;`gmyn%0uzhlZrdFrvBPKgZ?L<93_tQ-uA=)-sVI6UgA^1SN7Px%-|T?-+$I#N7ma@ejlv-d7MH+$&XLUZ"
    "bRNvd*;)5n4}45XPXYYsAKg$@<Yyj;=YRF@XBM$Ye%iq$Nl$d@1LZ*o|JBx_<8Y!{wMu@@6)O)EUPAbK(Qv=nv4JEP`Yjefg"
    "`NIbv@G;<-fOJnKfyeo{w)*+O}El-!omub$r*yzJ=?T`<Dg|EAZ_A6LCt{ZO^r(<C>Q5N#6|0{kx9kx`A+|3@nSeZh5W~m@+"
    "VE9i@#EtKtUIc5L;@8bc_S>D6d`rsG-C^E_sK4kqAuUd?d~Su0;RVHwk)o64)F^;>peIar|MdM?wy?F61%a|{pTpqKLVhJn)"
    "D#CHc%aLdoTE-v|jWm>LbNXEXfk0$~{TcC6uR`q?;a2@G;mRas!n)Ky(Fuv<E<C{+40|A!s9N#Jb{Rd0hwVD}to++K0U*6cV"
    "ENQr&Aw36!yKZ^?K%H-5-j?mV(zTfN`?CLGMPPIO#jH%*k%4I%rorLQ#ptH*AwJyl{IGVw)<u8>2AcA9-w$Z|1|fl&Kd^%t2"
    "Cm^+p5d3{M>@WNu7v}Do3--%03RtGN%u)<mGL7DAuY!?fgWJ29Dgtya9Q&t;OCl5{93;BTr9&eB_grhKb&TG2ocvtq?MmHP2"
    "VE3x&}g+!H?;B(m{Zl(&9EY5z?4~MBnsAGWN3_50-Hx`uCXlHr<+ZiGf_ikz+9a3nUBx!#F0#50)uC+cT}2Z(9Ku{|1@Jf#r"
    "ZAW_|RTy$xJq>axbfAMjy#uJ3t)>DO!~{y_}F1A_!XU|NiQg^lwR{?ZH>|6t<|+zb}>Em*+f{1=!27!Yh4J~O^&;GaZ<nOFt"
    "=Vuo9#m#|#5rC_@b*vnJ4m0bJ>phZj$4sZ?bx<F94hM*{MIQtl;FkFe)l^_|x@DK6=0t_sJOoKd79ruqX10UcC5JGNwd_yM{"
    "4{6A&`HcTCDhwCEP&JR6zgeqE#5hs2^qBYuv_W1j%ojL*F@?JM^GFO}Q1X!vJLD<I9oolm0@rsv9~}h&lRrRU_;Vqq^jUs1f"
    "JsCag((89jDJI=VA~PkK$FQ&NPOT8j~p0CVKeKuq-EOR0NeDe8nb@Gr<K*vxoL6yECX<x@F<g&XMpf_T#&pp2_%NW>4(6ndA"
    "@`ED*`4y!CeS2Ndg5?!11GR_^`a|+Cp;vH^3i0jDXe;nD~IKq09je7J|tiNT43%1^FOg@Jm?@hvzH$W%3h92LO<CmE}kDfSx"
    "5N$~R1gA7MX)m=7NZlIfoa8kRF0gZPERw`o{{G?+&WQ(m8ez{2DWL>Y|8^bfCMVIU}E5GH?HSi9j_1YY#Q>L-g{P7M-}=^xA"
    "q?gs`DDvUldDS1&~BEDGuhI4BOFvt^9s2sk1DNGZSM~XHX{E@%}h6p2u&-f3_gw&4UbwJ`}`vsI9A@X27pUJ=QIa~{U1UJ^$"
    "`~_VG+rp5bdM>^o-r#v(AjFycWFvo)@<sNtEG|BMAL$Fw#|i|;&mP=|2@;Ye_q^>>Yy&}9re|~Zcfqib5Qgb<^?`sqHYIT{v"
    "J7Ki^y&#>L8K>_&CmGAl%mHa72l^{H)mL6eAouqhW{uI8UFKwTHt#=MTyVoC*%gxb_Ie*xB-I?1P4+G2pmH){3Hbu6htgEBq"
    "EhrUk&;ONeH>s<@kv_2ZRy35r~-QP160~9$-gGCjSMXRRSgqz~G+(0Js8$!G?B?(|1%Cd8TIoUtIhkC`ehEkicC0)x5y4VP2"
    "E!AFjT^+zES-xpvKG_)j49!3m^NIQ@mHq=w~z-h7|qcVtc!HpHVSq6~(gkew)X;JPq*eoz7@K%_DH$s%E^R5Z$LvwR(s7nUE"
    "mq@e;y`pTl;NwxY1(hiVk!bnnp#2Ek60-YMtABt>_|6TA8mL`e982n=ChC^8dZzPu=sKg;Fc<?h*|AAY{1}0gOso&u=7xKaj"
    ")WPdRgX9lv>ofHm<_*}@l*VN1Z--K6Ks5lOfYGlt2q#bn@=PGO{RNkPk(3t6^B<Ixpwb1Y%M6(M&j$NJdIEufsVLi5s@(3YT"
    "P%)WV1D2iHKyxYjQ&J@j<UveP^XZRXZX!9lt6M-5mvUJNAd<0yyxRR!#@zd(r}QVU})iR^_hVlRD^@bnD~RLurvf9AsPOp+z"
    "(*@p=Pl91s%XWSeaF(FOtKqqD_=2D3zJ@BX0s(_&YMN1IM2#MkUEOY=Cg_1A$^==^jZ{2LJFcHa}doJHyS7m>vI2asbmmRtJ"
    "Xnhz3nV^M^HB-=o`rDiZ*J$uD>w>ZoQ=?ZK^&h)WfDf;1Ep|EOMQ3kRDAF2`Rs_U%x50)j9#lRtnglCL#aF%-jJo&bXeRH6D"
    "lr$3QZJVGc{$V~pRs5-WlP@pX+h93!-gkTbg?EFyUm=u|qgv0T#pbC%_qR-X$Bpg65kWdbCEmI#OHh@gir+oqjUkEzXcwiq`"
    "hx3o2gcbG%;A)0nEUG=>Tc38o3<h6_Tk<`Us8N;=gl~yb92-X-DiF!&OG^YKz-gO?TR-wP!h*KgoWQ6t`4Rf6MwLCiIDBH&s"
    "Otef0NCTMgWiBVi+EIU_6xwRq)tf0F#3^Fuc7EmF;qD|P(ITRluJ8!0mmOc#2HvnVvm@q&w+nT(4Y+jF8|PF09dhy&+HFcR9"
    "e8SzS^ba@Cnj1sJL*M$4M7qS#Y35dninOs5A*Suhsq~qc0%c;2hLuR9rI8;|8@k;F0?o{eYb<I0yUB0J3EAzfJ2SU5)iw2Dg"
    "8W+LAPqM3uqi2a=B<o`7iH;qVz)0Kdcr5WFYZ{TD#Mqy24ee^wWV7H!d+oPI(53>UgcvVdRtGdIP5E^W=4s?=uu1KI*LxS9a"
    "D`D1Sh8WMXz0lWVoP~Jc~Q1!|21Jny1CUTd8+rJ0!Op+%AL5tg;Ro{@rm4TW1E8qU6N|XD11NjXAA%Us>>MW!Gv4Lz;@<%1Z"
    ")h`0bgX>YEu=$5JMoHR9+UDlskJt-)Q>aie7iRwox*my%FrfB7)fB1L8{~JXauCW)wm!wPU}j%!u}W_Lo)o4<0!doj{sqzs^"
    "tnL?h=ALFA%qkDEY82C+P{ECr)^S~)6Z1mfge1V&94fd@Q(^$c7L6~fzk1(X>$8}^zo6Swy+#de`4l@Y~ruLVAhA3K?4PJnZ"
    ">uS_VtuH4cPqwRBwW)8#Nl9$JQ~yP}Ml(M=IK}0qg`SzqlO#q6C8aHJuu%JZ^s|p#4GAf2QQ>E0b(Y+heE$49<SY8@NJ-@VW"
    "hS*j>=4D5lAMJ}624D-nXv2VI8W!QYq|)#&W!d!YY7EuVJ3xcVKQ!5)Q2GDrjlrw^g+fDDR{z-RLpZ5;xe7Po%_Y+~*RFKn="
    "y%;%@bZEArI?Ll+(SH4B(lf+>2Glr)*O0~zu@S_nxVyWJJ4xfTnKnl~KkC~XyCk4U7Mg@#rV8*@xzA7*%fiv|J?OjQVA0S*Z"
    "&#V9Tr~coeX*0inO#ACtn-3L*9L4b?n1?pDkpD^NGy2!m8s4(G&!6*OQTEj*RAu=@!2C=vbL=I@Ue?%ac71kzc71kzc71kzc"
    "71kzc71kzc71kzc71kzc71kzc71kzc71kzc71kzc71kzc71kzc71kzc71kzcK!3e{@DM3fcj4n!>{r2$A7<o`~BtOYufdv&A"
    "!jt?@t`nzK?r-PuhOd;zhywGt6&*`@DJD*Z-*Tb=3HOBKR?%UjBL9_IuL)dnEi+2-8o;Z}O4F-)GHlPi1_}u1~(Me*M}s^Z%"
    "u8K5hE$^VSE?j(#(~5c=#%_y0xLzt38I@vN<H=HF+PKfj#zJNn;O{9@U6hQIOa=12kgFwYxbVE+8F@z>MF-$xz)S?8~5>v`J"
    "r^|Pk$XV+)?`RVFk=rGsq4FAt2zNF9|{L=B?44*Up{G9dOZ(AZmuw|_uAJRMgedJb)9;Khun@qhw#Jj&y@9?4<={Ur#^YmkW"
    "U)IX-^_KeaP<;>SHnG&74<2ZVKmMR)w8YPa_@z2`tVJWz?HKQ^)?e!pT6APhA$I9~cC7X9t=1vUqlItBaQ8gD!8Q7hK?S`zt"
    "2=3l-_9!zQTL1NI~d~_-F6Z^;QF!4=(hE3Tsdt0=b>5?zTRr-mH(W6mRXjs6h{@`uhP==nzH|+b<kahbi=V$E4NWdL;qDv-0"
    "ro+e`BSsKWbCz1-10t)PoypsNGifwbs=?Rc9>fEu)88*-}fJ^krJ3dho^u)|=7T^}~LLbWesQh-2TO<%=erp}T25>Z!xr0Qe"
    "E#Q)L|VeOs?rUo+_ap;`jXc3!PfJ^Phb>&Jfqn~Sr$6E*Xn3T<$4x21bgU%Tq$*VL3=ZWY&isOR%7`hM&^*pQF|i&c-cV0^g"
    "a<4n6>q3wnm+o1Qi7rvdZ1z$gC=~>b}nF8F$t@*nOd*9JsQv>D3YKhlrA>wzfRLw1iVx}J7Z50FL{{c38%s>"
)

_BC6H_CACHE = None
_BC7_CACHE = None


def load_bc6h():
    """Return `(endpoint_history, index_history, endpoint_class, index_class)`."""
    global _BC6H_CACHE
    if _BC6H_CACHE is None:
        raw = zlib.decompress(base64.b85decode(_BC6H_HISTORY_B85))
        eh_vals = struct.unpack_from("<3072H", raw, 0)
        endpoint_history = tuple(
            tuple(
                tuple(eh_vals[(k * 3 + c) * 4:(k * 3 + c + 1) * 4])
                for c in range(3)
            )
            for k in range(256)
        )
        index_history = tuple(
            tuple(raw[6144 + k * 16:6144 + (k + 1) * 16])
            for k in range(256)
        )
        endpoint_class = tuple(raw[10240:10496])
        index_class = tuple(raw[10496:10752])
        _BC6H_CACHE = (endpoint_history, index_history, endpoint_class, index_class)
    return _BC6H_CACHE


def load_bc7():
    """Return the decoded BC7 constant dictionary (cached on first call)."""
    global _BC7_CACHE
    if _BC7_CACHE is None:
        raw = zlib.decompress(base64.b85decode(_BC7_HISTORY_B85))

        def unpack_rows(offset, width):
            return [list(raw[offset + k * width:offset + (k + 1) * width]) for k in range(256)]

        endpoints = unpack_rows(0, 24)
        ep_bits = unpack_rows(6144, 24)
        ep_conf = unpack_rows(12288, 24)
        indices = unpack_rows(18432, 32)
        ix_bits = unpack_rows(26624, 32)
        ix_conf = unpack_rows(34816, 32)

        # Mid-range fill for endpoints known to 0 < d < 8 leading bits.
        # Readers taking <= d bits shift the low bits away unchanged.
        for row, depth in zip(endpoints, ep_bits):
            for j, d in enumerate(depth):
                if 0 < d < 8:
                    row[j] = (row[j] >> (8 - d) << (8 - d)) | (1 << (7 - d))

        lr_bytes = raw[43008:43776]
        last_resort = frozenset(
            (k, j)
            for k in range(256)
            for j in range(24)
            if (lr_bytes[(k * 24 + j) >> 3] >> ((k * 24 + j) & 7)) & 1
        )

        cells = sorted(
            ((a, b) for a in range(32) for b in range(16)),
            key=lambda ab: ((ab[0] + 1) * (ab[1] + 1), ab[0]),
        )
        rank_of = [-1] * 512
        for rank, (a, b) in enumerate(cells[:len(BC7_CONFIG)]):
            rank_of[a * 16 + b] = rank

        partition2 = tuple(
            tuple((mask >> p) & 1 for p in range(16))
            for mask in _BC7_PART2_PACKED
        )
        partition3 = tuple(
            tuple((mask >> (2 * p)) & 3 for p in range(16))
            for mask in _BC7_PART3_PACKED
        )

        _BC7_CACHE = {
            "config": BC7_CONFIG,
            "rank_of": tuple(rank_of),
            "inferred": BC7_CONFIG_INFERRED,
            "partition2": partition2,
            "partition3": partition3,
            "anchor2": BC7_ANCHOR2,
            "anchor3a": BC7_ANCHOR3A,
            "anchor3b": BC7_ANCHOR3B,
            "history_endpoints": tuple(tuple(r) for r in endpoints),
            "history_endpoint_bits": tuple(tuple(r) for r in ep_bits),
            "history_endpoint_confirmed_bits": tuple(tuple(r) for r in ep_conf),
            "history_indices": tuple(tuple(r) for r in indices),
            "history_index_bits": tuple(tuple(r) for r in ix_bits),
            "history_index_confirmed_bits": tuple(tuple(r) for r in ix_conf),
            "last_resort": last_resort,
        }
    return _BC7_CACHE
````
